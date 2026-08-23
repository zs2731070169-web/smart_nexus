import asyncio

import httpx

from infra.logging.logger import log
from infra.tools import tool_registry


def proxy_client_factory(
        headers: dict[str, str] | None = None,
        timeout: httpx.Timeout | None = None,
        auth: httpx.Auth | None = None,
) -> httpx.AsyncClient:
    """配置代理工厂，忽略系统代理环境变量（HTTP_PROXY / HTTPS_PROXY），避免代理导致的 TLS 连接失败"""
    return httpx.AsyncClient(
        headers=headers,
        timeout=timeout,
        auth=auth,
        trust_env=False,
    )


# 探测超时（秒）：真实网络请求的上限，防止心跳被挂死的连接卡住
_PROBE_TIMEOUT = 30

# 心跳探测间隔（秒），需小于 client_session_timeout_seconds=120，避免会话过期
_HEARTBEAT_INTERVAL = 60


async def _probe(server, name: str) -> bool:
    """探测单个 MCP 连接是否存活。
    直接调用底层 mcp ClientSession.list_tools() 发起真实网络请求：
    - 绕开 agents SDK 的工具列表缓存（缓存命中无法证明连接存活）
    - agents 0.1.0 的 server.list_tools() 需要 run_context/agent 参数，探测场景不可用
    """
    session = getattr(server, "session", None)
    if session is None:
        log.warning(f"{name} MCP探测失败: 会话不存在")
        return False
    try:
        await asyncio.wait_for(session.list_tools(), timeout=_PROBE_TIMEOUT)
        log.info(f"{name} MCP探测成功...")
        return True
    except asyncio.CancelledError:
        raise
    except Exception as e:
        log.warning(f"{name} MCP探测失败: {e}")
        return False


async def _reconnect(server, name: str) -> None:
    """对单个 MCP 实例执行重连（cleanup → connect → 清工具缓存）"""
    log.warning(f"{name} MCP连接断开，尝试重连...")
    try:
        await server.cleanup()
    except Exception as e:
        # cleanup 失败不阻断重连，仅记录
        log.debug(f"{name} MCP cleanup异常（已忽略）: {e}")
    try:
        await server.connect()
        # cache_tools_list=True 时 SDK 仍持有旧会话的工具列表缓存，重连后必须失效
        server.invalidate_tools_cache()
        log.info(f"{name} MCP重连成功")
    except asyncio.CancelledError:
        raise
    except Exception as e:
        log.error(f"{name} MCP重连失败，将在下次心跳重试: {e}")


async def manage_connections(interval: int = _HEARTBEAT_INTERVAL,
                             first_round_done: asyncio.Event | None = None,
                             init_error: list | None = None) -> None:
    """MCP 连接生命周期管理任务：建立连接 → 周期探活 → 断开自动重连 → 退出时统一关闭。

    连接的建立、重连、关闭必须在同一个任务内完成：anyio cancel scope 与任务绑定，
    若在其他任务（如请求处理任务、心跳任务交叉）里 exit，会触发
    "Attempted to exit cancel scope in a different task than it was entered in"，
    并连带取消建立连接的原任务（曾导致 lifespan 被心跳任务意外取消、MCP 会话全部失效）。

    :param interval: 探活间隔（秒）
    :param first_round_done: 首轮连接结束信号（无论成败都会 set）
    :param init_error: 首轮连接异常传出（空列表 = 成功），供 lifespan 判断启动结果
    """
    mcp_servers = tool_registry.mcp_servers()
    try:
        # 启动阶段：建立全部连接，任一失败即带异常结束（lifespan 据此中止服务启动）
        try:
            for server in mcp_servers:
                try:
                    await server.connect()
                    log.info(f"MCP {server.name} 连接初始化成功")
                except asyncio.CancelledError:
                    log.error("初始化 MCP 连接被取消")
                    raise
                except Exception as e:
                    log.error(f"MCP {server.name} 连接初始化失败，终止服务启动: {e}")
                    raise
        except BaseException as e:
            if init_error is not None:
                init_error.append(e)
            raise
        finally:
            if first_round_done is not None:
                first_round_done.set()

        log.info(f"MCP心跳任务启动，探测间隔 {interval}s")
        # 运行阶段：周期探活，断开自动重连
        while True:
            await asyncio.sleep(interval)
            for server in tool_registry.mcp_servers():
                name = getattr(server, "name", server.__class__.__name__)
                if not await _probe(server, name):
                    await _reconnect(server, name)
    finally:
        # 任务退出（正常/异常/取消）时统一关闭连接；与建立连接同任务，cancel scope 安全
        for server in mcp_servers:
            try:
                await server.cleanup()
                log.info(f"MCP {server.name} 连接关闭成功")
            except asyncio.CancelledError:
                # 关闭途中再次收到取消信号：吞掉并继续清理其余连接
                pass
            except Exception as e:
                log.debug(f"MCP {server.name} 连接关闭异常（已忽略）: {e}")
