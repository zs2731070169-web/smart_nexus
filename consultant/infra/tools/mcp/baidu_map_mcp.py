"""
百度地图 MCP
"""
from agents.mcp import MCPServerStreamableHttp, MCPServerStreamableHttpParams

from config.settings import settings
from infra.client.mcp_client import _no_proxy_client_factory

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