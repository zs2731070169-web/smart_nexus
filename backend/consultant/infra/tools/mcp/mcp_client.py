import asyncio

import httpx
from agents.mcp import MCPServerStreamableHttp, MCPServerStreamableHttpParams

from config.settings import settings
from infra.logging.logger import log


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


"""
tavily联网搜索 MCP
"""
web_search_mcp = MCPServerStreamableHttp(
    name="tavily联网搜索",
    params=MCPServerStreamableHttpParams(
        url=f"{settings.TAVILY_BASE_URL}?tavilyApiKey={settings.TAVILY_API_KEY}",
        timeout=60,
        sse_read_timeout=60,
        httpx_client_factory=_no_proxy_client_factory,
    ),
    client_session_timeout_seconds=120,
    cache_tools_list=True
)

"""
百度地图 MCP
"""
baidu_map_mcp = MCPServerStreamableHttp(
    name="百度地图搜索",
    params=MCPServerStreamableHttpParams(
        url=f"{settings.BAIDUMAP_BASE_URL}?ak={settings.BAIDUMAP_AK}",
        timeout=60,
        sse_read_timeout=60,
        httpx_client_factory=_no_proxy_client_factory,
    ),
    client_session_timeout_seconds=120,
    cache_tools_list=True
)


# 初始化连接
async def connect():
    try:
        await web_search_mcp.connect()
        log.info("成功连接tavily联网搜索MCP")
    except asyncio.CancelledError:
        # anyio cancel scope 取消信号，必须重新抛出，不能吞掉
        log.error("连接tavily联网搜索MCP被anyio cancel scope取消")
        raise
    except Exception as e:
        log.error(f"连接tavily联网搜索MCP失败: {e}")
        raise
    try:
        await baidu_map_mcp.connect()
        log.info("成功连接百度地图搜索MCP")
    except asyncio.CancelledError:
        log.error("连接百度地图搜索MCP被anyio cancel scope取消")
        raise
    except Exception as e:
        log.error(f"连接百度地图搜索MCP失败: {e}")
        raise


# 关闭连接
async def disconnect():
    try:
        await web_search_mcp.cleanup()
        log.info("成功断开连接tavily联网搜索MCP")
    except asyncio.CancelledError:
        log.warning("断开tavily联网搜索MCP被anyio cancel scope取消")
        raise
    except Exception as e:
        log.error(f"断开连接tavily联网搜索MCP失败: {e}")
        raise
    try:
        await baidu_map_mcp.cleanup()
        log.info("成功断开连接百度地图搜索MCP")
    except asyncio.CancelledError:
        log.warning("断开百度地图搜索MCP被anyio cancel scope取消")
        raise
    except Exception as e:
        log.error(f"断开连接百度地图搜索MCP失败: {e}")
        raise


# 心跳探测间隔（秒），需小于 client_session_timeout_seconds=120，避免会话过期
_HEARTBEAT_INTERVAL = 60

# 所有受管 MCP 实例
_MCP_SERVERS = [
    (web_search_mcp, "tavily联网搜索"),
    (baidu_map_mcp, "百度地图搜索"),
]


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


async def heartbeat(interval: int = _HEARTBEAT_INTERVAL) -> None:
    """MCP心跳任务：定期探活，连接断开时自动重连。
    由 lifespan 通过 asyncio.create_task() 在后台运行，随服务关闭时取消。
    """
    log.info(f"MCP心跳任务启动，探测间隔 {interval}s")
    while True:
        await asyncio.sleep(interval)
        for server, name in _MCP_SERVERS:
            if not await _probe(server, name):
                await _reconnect(server, name)
