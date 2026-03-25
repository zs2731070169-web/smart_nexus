from agents import OpenAIChatCompletionsModel
from openai import AsyncOpenAI

from config.settings import settings

# sf_llm_client = AsyncOpenAI(
#     api_key=settings.SF_API_KEY,
#     base_url=settings.SF_BASE_URL,
# )

al_llm_client = AsyncOpenAI(
    api_key=settings.AL_BAILIAN_API_KEY,
    base_url=settings.AL_BAILIAN_BASE_URL,
)

# 硅基流动模型推理模型，用于协调agent
main_model = OpenAIChatCompletionsModel(model=settings.MAIN_MODEL_NAME, openai_client=al_llm_client)

# 阿里千问模型通用模型，用于所有agent
sub_model = OpenAIChatCompletionsModel(model=settings.SUB_MODEL_NAME, openai_client=al_llm_client)
