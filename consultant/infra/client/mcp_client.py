import asyncio

import httpx

from infra.logging.logger import log
from infra.tools import tool_registry


# 配置代理工厂，不走系统代理
def _no_proxy_client_factory(
        headers: dict[str, str] | None = None,
        timeout: httpx.Timeout | None = None,
        auth: httpx.Auth | None = None,
) -> httpx.AsyncClient:
    """创建不使用系统代理的 httpx 客户端，避免代理导致的 TLS 连接失败"""
    return httpx.AsyncClient(
        headers=headers,
        timeout=timeout,
        auth=auth,
        trust_env=False,  # 忽略系统代理环境变量（HTTP_PROXY / HTTPS_PROXY）
    )


# 初始化连接
async def connect():
    mcp_servers = tool_registry.mcp_servers()
    for server in mcp_servers:
        try:
            await server.connect()
            log.info(f"MCP {server.name} 连接初始化成功")
        except asyncio.CancelledError:
            log.error("初始化 MCP 连接被取消")
            raise
        except Exception as e:
            # 任一 MCP 连接失败即向上抛出，由 lifespan 终止服务启动
            log.error(f"MCP {server.name} 连接初始化失败，终止服务启动: {e}")
            raise


# 关闭连接
async def disconnect():
    mcp_servers = tool_registry.mcp_servers()
    try:
        for server in mcp_servers:
            await server.cleanup()
            log.info(f"MCP {server.name} 连接关闭成功")
    except asyncio.CancelledError as e:
        log.error(f"关闭 MCP 连接发生异常")
        raise


async def _probe(server, name: str) -> bool:
    """探测单个 MCP 连接是否存活。
    清除 SDK 内部工具列表缓存后调用 list_tools()，强制发起真实网络请求而非命中缓存。
    """
    try:
        # openai-agents SDK 将缓存存储在 _tools 属性；清除后 list_tools() 会重新请求
        if hasattr(server, '_tools'):
            server._tools = None
        await server.list_tools()
        log.info(f"{name} MCP探测成功...")
        return True
    except asyncio.CancelledError:
        raise
    except Exception as e:
        log.warning(f"{name} MCP探测失败: {e}")
        return False


async def _reconnect(server, name: str) -> None:
    """对单个 MCP 实例执行重连（cleanup → connect）"""
    log.warning(f"{name} MCP连接断开，尝试重连...")
    try:
        await server.cleanup()
    except Exception as e:
        # cleanup 失败不阻断重连，仅记录
        log.debug(f"{name} MCP cleanup异常（已忽略）: {e}")
    try:
        await server.connect()
        log.info(f"{name} MCP重连成功")
    except asyncio.CancelledError:
        raise
    except Exception as e:
        log.error(f"{name} MCP重连失败，将在下次心跳重试: {e}")


# 心跳探测间隔（秒），需小于 client_session_timeout_seconds=120，避免会话过期
_HEARTBEAT_INTERVAL = 60


async def heartbeat(interval: int = _HEARTBEAT_INTERVAL) -> None:
    """MCP心跳任务：定期探活，连接断开时自动重连。
    由 lifespan 通过 asyncio.create_task() 在后台运行，随服务关闭时取消。
    """
    log.info(f"MCP心跳任务启动，探测间隔 {interval}s")
    while True:
        await asyncio.sleep(interval)
        for server in tool_registry.mcp_servers():
            name = getattr(server, "name", server.__class__.__name__)
            if not await _probe(server, name):
                await _reconnect(server, name)
