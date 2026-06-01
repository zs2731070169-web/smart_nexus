from typing import Optional

from pydantic import Field, BaseModel


class ChatRequest(BaseModel):
    """用户对话请求"""
    query: str = Field(..., description="用户的咨询问题")

    session_id: Optional[str] = Field(default=None, description="多轮会话携带的会话id")

    # 前端 GPS 定位（可选），作为导航起点的最高优先级信号；缺省时后端走 IP/兜底降级
    lng: Optional[float] = Field(default=None, description="前端定位经度")

    lat: Optional[float] = Field(default=None, description="前端定位纬度")

    # 保留字段
    coord_type: Optional[str] = Field(default=None, description="坐标系：wgs84(浏览器)/gcj02(高德/小程序)，缺省按 wgs84 处理")


class CodeRequest(BaseModel):
    """用户登录请求"""
    user_phone: str = Field(..., description="用户手机号")


class LoginRequest(BaseModel):
    """用户登录请求"""
    user_phone: str = Field(..., description="用户手机号")

    code: str = Field(..., description="验证码")
