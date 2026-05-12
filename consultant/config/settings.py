from pathlib import Path
from typing import Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Consultant 模块配置（仅包含智能顾问相关配置项）"""

    # ============================== 模型服务商配置 ==============================
    API_KEY: Optional[str] = Field(description="API Key")
    BASE_URL: Optional[str] = Field(description="Base URL")
    # 主模型：用于 coordination_agent，需支持 enable_thinking 才能输出原生思维链
    MAIN_MODEL_NAME: Optional[str] = Field(description="协调模型（需支持 thinking）")
    # 子模型：用于 consult_agent / navigation_agent，普通对话模型即可
    SUB_MODEL_NAME: Optional[str] = Field(description="工作模型")

    # ============================== 数据库配置 ==============================

    MYSQL_HOST: Optional[str] = Field(default="localhost", description="MySQL 主机地址")
    MYSQL_PORT: Optional[int] = Field(default=3306, description="MySQL 端口")
    MYSQL_USER: Optional[str] = Field(default="root", description="MySQL 用户名")
    MYSQL_PASSWORD: Optional[str] = Field(default="123456", description="MySQL 密码")
    MYSQL_DATABASE: Optional[str] = Field(default="smart_nexus", description="MySQL 数据库名称")
    MYSQL_CHARSET: Optional[str] = Field(default="utf8mb4", description="MySQL 字符集")
    MYSQL_CONNECT_TIMEOUT: Optional[int] = Field(default=10, description="MySQL 连接超时时间（秒）")
    MYSQL_MAX_CONNECTIONS: Optional[int] = Field(default=5, description="MySQL 最大连接数")

    # ============================== MCP 配置 ==============================

    TAVILY_BASE_URL: Optional[str] = Field(default="https://mcp.tavily.com/mcp",
                                           description="tavily搜索 MCP URL")
    TAVILY_API_KEY: Optional[str] = Field(default="", description="Tavily API Key")

    BAIDUMAP_BASE_URL: Optional[str] = Field(default="https://mcp.map.baidu.com/mcp",
                                             description="百度地图搜索 MCP URL")
    BAIDUMAP_AK: Optional[str] = Field(default="", description="百度地图 AK")

    # ============================== Redis 配置 ==============================

    REDIS_HOST: Optional[str] = Field(default="127.0.0.1", description="Redis 主机地址")
    REDIS_PORT: Optional[int] = Field(default=6379, description="Redis 端口")
    REDIS_PASSWORD: Optional[str] = Field(default=None, description="Redis 密码（无密码时留空）")
    REDIS_DB: Optional[int] = Field(default=0, description="Redis 数据库编号")
    REDIS_MAX_CONNECTIONS: Optional[int] = Field(default=10, description="Redis 连接池最大连接数")

    # ============================== 本地知识库 URL ==============================

    KNOWLEDGE_BASE_URL: Optional[str] = Field(
        default="http://localhost:8000/smart/nexus/knowledge/retrieval/query",
        description="知识库服务 URL"
    )

    # ============================== 文件路径 ==============================

    PROMPTS_FILE_DIR: str = str(Path(__file__).parent.parent / "prompts")
    HISTORY_FILE_DIR: str = str(Path(__file__).parent.parent / "history")

    # ============================== 记忆压缩配置 ==============================
    # 历史消息 token 估算超过该阈值时，下次 save_history 触发 LLM 结构化摘要
    MEMORY_COMPRESS_THRESHOLD_TOKENS: int = Field(default=8000, description="触发上下文压缩的 token 阈值")
    # tail 段按 token 预算反向累加，保护近期对话不被压缩
    MEMORY_COMPRESS_TAIL_TOKENS: int = Field(default=2000, description="压缩时保护近期对话的 token 预算")
    # head 段保护的非系统消息条数（首轮 user+assistant 作为任务/指代锚点，2 条避免出现连续同角色）
    MEMORY_COMPRESS_HEAD_N: int = Field(default=2, description="压缩时保护头部对话的条数")

    # ============================== 登陆验证 ==============================

    SECRET_KEY: str = Field(default="", description="登录使用的私钥")
    ALGORITHM: str = Field(default="HS256", description="加密和解密算法")
    TOKEN_EXPIRE_HOURS: int = Field(default=24, description="token有效期")

    # ============================== 免登陆名单 ==============================

    WHITE_LIST: set[str] = Field(
        default=["/smart/nexus/consultant/code", "/smart/nexus/consultant/login"],
        description="免登录验证的接口列表")

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent.parent / ".env"),
        extra="ignore",
        env_file_encoding="utf-8",
        case_sensitive=True,
        validate_default=True
    )

    @model_validator(mode="after")
    def validation_default_value(self):
        """settings 实例创建以后执行该方法校验默认值"""
        required_fields = {
            "API_KEY": self.API_KEY,
            "BASE_URL": self.BASE_URL,
            "MAIN_MODEL_NAME": self.MAIN_MODEL_NAME,
            "SUB_MODEL_NAME": self.SUB_MODEL_NAME,
        }
        missing = [name for name, value in required_fields.items() if not value or not value.strip()]
        if missing:
            raise ValueError(f"以下配置项必须配置且不能为空：{', '.join(missing)}")

        return self


settings = Settings()
