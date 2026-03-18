import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Knowledge 模块配置（仅包含知识库相关配置项）"""

    # ============================== LLM 模型配置 ==============================

    API_KEY: str = Field(default="", description="模型密钥")
    BASE_URL: str = Field(default="https://api.openai-proxy.org/v1", description="模型地址")
    MODEL: str = Field(default="gpt-4o-mini", description="语言模型")
    EMBEDDING_MODEL: str = Field(default="text-embedding-3-large", description="嵌入模型")

    # ============================== 爬虫数据源 ==============================

    KNOWLEDGE_BASE_URL: str = Field(
        default="https://iknow.lenovo.com.cn",
        description="爬取第三方知识库的 URL"
    )

    # ============================== 路径配置 ==============================

    _current_dir = os.path.dirname(os.path.abspath(__file__))
    _knowledge_dir = os.path.dirname(_current_dir)  # knowledge/ 目录

    # Chroma 向量文件存放路径
    VECTOR_STORE_PATH: str = os.path.join(_knowledge_dir, "chroma_kb")

    # 爬取文件目录
    CRAWL_OUTPUT_DIR: str = os.path.join(_knowledge_dir, "data", "crawl")

    # md 文件目录
    MD_FOLDER_PATH: str = CRAWL_OUTPUT_DIR

    # 文件临时存储目录
    TMP_OUTPUT_DIR: str = os.path.join(_knowledge_dir, "data", "tmp")

    # ============================== 文本处理配置 ==============================

    # 文本拆分长度
    CHUNK_SIZE: int = 3000
    CHUNK_OVERLAP: int = 300

    # 检索后排序数量
    TOP_ROUGH: int = 50
    TOP_FINAL: int = 5

    model_config = SettingsConfigDict(
        env_file=os.path.join(_knowledge_dir, ".env"),
        extra="ignore",
        env_file_encoding="utf-8"
    )


settings = Settings()
