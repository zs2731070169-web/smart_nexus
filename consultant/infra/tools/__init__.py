from infra.logging.logger import log
from infra.tools.base import tool_registry
from infra.tools.local.navigation_sites import navigation_sites
from infra.tools.local.retrieval_knowledge import retrieval_knowledge
from infra.tools.local.search_coordinate_source import search_coordinate_source
from infra.tools.mcp.baidu_map_mcp import baidu_map_mcp
from infra.tools.mcp.web_search_mcp import web_search_mcp

tool_registry.register(retrieval_knowledge)
tool_registry.register(search_coordinate_source)
tool_registry.register(navigation_sites)
tool_registry.register_mcp(web_search_mcp)
tool_registry.register_mcp(baidu_map_mcp)
log.info("工具注册完毕")