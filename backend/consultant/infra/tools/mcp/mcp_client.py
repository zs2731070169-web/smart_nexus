from agents.mcp import MCPServerStreamableHttp, MCPServerStreamableHttpParams

from config.settings import settings

"""
tavily联网搜索 MCP
"""
web_search_mcp = MCPServerStreamableHttp(
    name="tavily联网搜索",
    params=MCPServerStreamableHttpParams(
        url=f"{settings.TAVILY_BASE_URL}?tavilyApiKey={settings.TAVILY_API_KEY}",
        timeout=60,
        sse_read_timeout=60
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
        sse_read_timeout=60
    ),
    client_session_timeout_seconds=120,
    cache_tools_list=True
)
