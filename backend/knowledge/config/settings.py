import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # 模型配置
    API_KEY: str # 模型密钥
    BASE_URL: str # 模型地址
    MODEL: str # 语言模型
    EMBEDDING_MODEL: str  # 嵌入模型

    # 知识库线上数据集
    KNOWLEDGE_BASE_URL: str

    _current_dir = os.path.dirname(os.path.abspath(__file__))
    _knowledge_dir = os.path.dirname(_current_dir)  # knowledge/ 目录
    _backend_dir = os.path.dirname(_knowledge_dir)   # backend/ 目录

    # Chroma向量文件存放路径
    VECTOR_STORE_PATH: str = os.path.join(_knowledge_dir, "chroma_kb")

    # 爬取文件目录
    CRAWL_OUTPUT_DIR: str = os.path.join(_knowledge_dir, "data", "crawl")

    # md文件目录
    MD_FOLDER_PATH: str = CRAWL_OUTPUT_DIR

    # 文件临时存储目录
    TMP_OUTPUT_DIR: str = os.path.join(_knowledge_dir, "data", "tmp")

    # 文本拆分长度
    CHUNK_SIZE: int = 3000
    CHUNK_OVERLAP: int = 300

    # 检索后排序数量
    TOP_ROUGH: int = 50
    TOP_FINAL: int = 5

    model_config = SettingsConfigDict(
        env_file=os.path.join(_knowledge_dir, ".env"), # env文件在 knowledge/ 下（与 setup.py 同级）
        extra = "ignore", # settings.py配置忽略.env中未定义的环境变量
        env_file_encoding = "utf-8"
    )


settings = Settings()



