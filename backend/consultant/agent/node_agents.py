from agents import Agent, ModelSettings

from config.settings import settings
from infra.ai.ai_client import al_chat_completions
from infra.tools.local.map_navigation import search_coordinate_source, navigation_sites
from infra.tools.local.retrieval_knowledge import retrieval_knowledge
from infra.tools.mcp.mcp_client import web_search_mcp, baidu_map_mcp
from utils.file_utils import load_prompt

# 售后咨询agent
consult_agent = Agent(
    name="consult_agent",
    instructions=load_prompt(settings.PROMPTS_FILE_DIR + "/consult_agent.md"),
    model=al_chat_completions,
    tools=[retrieval_knowledge],
    mcp_servers=[web_search_mcp],
    model_settings=ModelSettings(
        temperature=0
    )
)

# 服务站点导航agent
navigation_agent = Agent(
    name="navigation_agent",
    instructions=load_prompt(settings.PROMPTS_FILE_DIR + "/navigation_agent.md"),
    model=al_chat_completions,
    tools=[search_coordinate_source, navigation_sites],
    mcp_servers=[baidu_map_mcp],
    model_settings=ModelSettings(
        temperature=0
    )
)