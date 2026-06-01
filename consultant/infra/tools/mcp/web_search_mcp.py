"""
tavily联网搜索 MCP
"""
from agents.mcp import MCPServerStreamableHttp, MCPServerStreamableHttpParams

from config.settings import settings
from infra.client.mcp_client import proxy_client_factory


web_search_mcp = MCPServerStreamableHttp(
    name="tavily联网搜索",
    params=MCPServerStreamableHttpParams(
        url=f"{settings.TAVILY_BASE_URL}?tavilyApiKey={settings.TAVILY_API_KEY}",
        timeout=60,
        sse_read_timeout=60,
        httpx_client_factory=proxy_client_factory,
    ),
    client_session_timeout_seconds=120,
    cache_tools_list=True
)