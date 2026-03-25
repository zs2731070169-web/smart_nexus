# 协调agent

from agents import Agent, ModelSettings

from agent.agent_router import AGENT_ROUTER
from config.settings import settings
from infra.ai.ai_client import main_model
from utils.file_utils import load_file

coordination_agent = Agent(
    name="coordination_agent",
    instructions=load_file(settings.PROMPTS_FILE_DIR + "/coordination_agent.md"),
    model=main_model,
    tools=AGENT_ROUTER,
    model_settings=ModelSettings(temperature=0)
)


