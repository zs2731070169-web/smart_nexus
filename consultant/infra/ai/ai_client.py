from agents import OpenAIChatCompletionsModel
from openai import AsyncOpenAI

from config.settings import settings

llm_client = AsyncOpenAI(
    api_key=settings.API_KEY,
    base_url=settings.BASE_URL,
)

# 用于协调agent
main_model = OpenAIChatCompletionsModel(model=settings.MAIN_MODEL_NAME, openai_client=llm_client)

# 用于所有agent
sub_model = OpenAIChatCompletionsModel(model=settings.SUB_MODEL_NAME, openai_client=llm_client)
