# 协调agent

from agents import Agent, ModelSettings

from agent.agent_router import agent_router_registry
from config.settings import settings
from infra.client.ai_client import main_model
from utils.file_utils import load_file

coordination_agent = Agent(
    name="coordination_agent",
    instructions=load_file(settings.PROMPTS_FILE_DIR + "/coordination_agent.md"),
    model=main_model,
    tools=agent_router_registry.routes(),
    model_settings=ModelSettings(temperature=0.3)
)


