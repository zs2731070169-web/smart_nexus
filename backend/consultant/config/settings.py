from pathlib import Path
from typing import Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ==============================模型服务商配置==============================

    SF_API_KEY: Optional[str] = Field(default="", description="硅基流动 API Key")
    SF_BASE_URL: Optional[str] = Field(default="https://api.siliconflow.cn/v1", description="硅基流动 Base URL")
    MAIN_MODEL_NAMEP: Optional[str] = Field(default="Qwen/Qwen3-32B", description="硅基流动模型")

    AL_BAILIAN_API_KEY: Optional[str] = Field(default="", description="百链 API Key")
    AL_BAILIAN_BASE_URL: Optional[str] = Field(default="https://dashscope.aliyuncs.com/compatible-mode/v1",
                                               description="百链 Base URL")
    SUB_MODEL_NAME: Optional[str] = Field(default="qwen3-max", description="百链模型")

    # ==============================数据库科配置==============================

    MYSQL_HOST: Optional[str] = Field(default="localhost", description="MySQL 主机地址")
    MYSQL_PORT: Optional[int] = Field(default=3306, description="MySQL 端口")
    MYSQL_USER: Optional[str] = Field(default="root", description="MySQL 用户名")
    MYSQL_PASSWORD: Optional[str] = Field(default="root", description="MySQL 密码")
    MYSQL_DATABASE: Optional[str] = Field(default="smart_nexus", description="MySQL 数据库名称")
    MYSQL_CHARSET: Optional[str] = Field(default="utf8mb4", description="MySQL 字符集")
    MYSQL_CONNECT_TIMEOUT: Optional[int] = Field(default=10, description="MySQL 连接超时时间（秒）")
    MYSQL_MAX_CONNECTIONS: Optional[int] = Field(default=5, description="MySQL 最大连接数")

    # ==============================MCP配置==============================

    DASHSCOPE_BASE_URL: Optional[str] = Field(default="https://dashscope.aliyuncs.com/api/v1/mcps/WebSearch/sse",
                                              description="百炼搜索MCP URL")
    BAIDUMAP_AK: Optional[str] = Field(default="", description="百度地图 AK")

    # ==============================本地知识库URL==============================

    KNOWLEDGE_BASE_URL: Optional[str] = Field(default="http://localhost:8000/smart/nexus/knowledge/retrieval/query",
                                              description="知识库服务 URL")

    config = SettingsConfigDict(
        env_file=str(Path(__file__).parent.parent / ".env"),
        json_file_encoding="utf-8",
        case_sensitive=True,  # 环境变量名大小写敏感
        extra="ignore",  # settings.py配置忽略.env中未定义的环境变量
        validate_default=True  # 验证默认值
    )

    @model_validator(mode="after")
    def validation_default_value(self):
        """
        settings实例创建以后执行该方法校验默认值
        :return:
        """
        is_valid = any([self.SF_API_KEY or self.SF_BASE_URL.strip(),
                        self.AL_BAILIAN_API_KEY or self.AL_BAILIAN_API_KEY.strip(),
                        self.BAIDUMAP_AK or self.BAIDUMAP_AK.strip()])

        if not is_valid:
            raise ValueError("API KEY 无效")


settings = Settings()
