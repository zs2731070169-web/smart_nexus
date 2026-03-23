from typing import Optional

from pydantic import Field, BaseModel


class ChatRequest(BaseModel):
    """用户对话请求"""
    query: str = Field(..., description="用户的咨询问题")

    session_id: Optional[str] = Field(default=None, description="多轮会话携带的会话id")

    ip: Optional[str] = Field(default=None, description="用户真实ip")


class CodeRequest(BaseModel):
    """用户登录请求"""
    user_phone: str = Field(..., description="用户手机号")


class LoginRequest(BaseModel):
    """用户登录请求"""
    user_phone: str = Field(..., description="用户手机号")

    code: str = Field(..., description="验证码")
