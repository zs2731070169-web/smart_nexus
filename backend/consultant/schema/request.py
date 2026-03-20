from typing import Optional

from pydantic import Field, BaseModel


class UserContext(BaseModel):
    """用户上下文消息的标识"""
    user_id: str = Field(..., description="用户登录的唯一id")

    session_id: Optional[str] = Field(default=None, description="多轮会话携带的会话id")


class ChatRequest(BaseModel):
    """用户对话请求"""
    query: str = Field(..., description="用户的咨询问题")

    user_context: UserContext = Field(..., description="用户上下文信息")


class SessionRequest(BaseModel):
    """会话列表查询请求"""
    user_id: str = Field(..., description="用户登录的唯一id")
