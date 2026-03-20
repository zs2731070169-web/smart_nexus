# 协调agent

from agents import Agent, ModelSettings

from agent.agent_router import AGENT_ROUTER
from config.settings import settings
from infra.ai.ai_client import al_chat_completions
from utils.file_utils import load_prompt

coordination_agent = Agent(
    name="coordination_agent",
    instructions=load_prompt(settings.PROMPTS_FILE_DIR + "/coordination_agent.md"),
    model=al_chat_completions,
    tools=AGENT_ROUTER,
    model_settings=ModelSettings(temperature=0)
)


