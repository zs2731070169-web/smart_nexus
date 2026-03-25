import uuid
from datetime import datetime
from typing import Literal, Union, Optional

from pydantic import BaseModel, Field

from constants.enums import RenderType, StreamStatus, FinishedReason


class MessageType(BaseModel):
    """消息类型"""
    message_type: str = Field(description='消息类型，分片消息为delta，结束消息为finish')


class DeltaMessage(MessageType):
    """分片消息"""
    message_type: Literal['delta'] = Field(default='delta', description='消息类型')

    render_type: RenderType = Field(description="分情况渲染：THINKING/PROCESSING/ANSWER")

    data: str = Field(description="文本内容")


class FinishMessage(MessageType):
    """结束消息"""
    message_type: Literal['finish'] = Field(default='finish', description='消息类型')


class Metadata(BaseModel):
    """流式输出数据对象的元数据"""
    create_time: str = Field(default="", description="消息创建时间")

    finished_reason: Optional[FinishedReason] = Field(default=None,
                                                      description="agent结束原因，NORMAL/EXCEPTION/MAX_TOKEN")

    error_message: Optional[str] = Field(default=None,
                                         description="如果stop_reason是EXCEPTION，这里会有错误信息；否则为空字符串")


class StreamMessages(BaseModel):
    """流式输出的数据对象"""
    id: str = Field(description="流式输出的数据对象id")

    data: Union[DeltaMessage, FinishMessage] = Field(description="流式输出的数据对象，包含分片消息和结束消息两种类型")

    status: StreamStatus = Field(description="流式状态，控制SSE生命周期，PROCESSING/FINISHED")

    metadata: Metadata = Field(description="流式输出数据对象的元数据")

    @classmethod
    def build_processing(cls, data: str, render_type: RenderType) -> "StreamMessages":
        """构建分片消息"""
        if not isinstance(render_type, RenderType):
            raise TypeError("render_type 必须是 RenderType 枚举")

        return cls(
            id=uuid.uuid4().hex,
            data=DeltaMessage(data=data, render_type=render_type),
            status=StreamStatus.PROCESSING,
            metadata=Metadata(create_time=str(datetime.now())),
        )

    @classmethod
    def build_finished(cls,
                       message_id: Optional[str] = None,
                       finished_reason: FinishedReason = None,
                       error_message=None) -> "StreamMessages":
        """构建结束消息"""
        return cls(
            id=message_id or uuid.uuid4().hex,
            data=FinishMessage(),
            status=StreamStatus.FINISHED,
            metadata=Metadata(
                create_time=str(datetime.now()),
                finished_reason=finished_reason,
                error_message=error_message
            ),
        )


class SystemResp(BaseModel):
    """
    系统响应字段
    """
    status: str = Field(default="200", description="响应状态")

    message: str = Field(default="", description="响应消息")


class ChatHistoryResp(SystemResp):
    """
    用户聊天历史列表
    """
    chat_history_list: list[dict] = Field(description="历史会话列表，包含session_id、file_time、history_list信息")


class LoginResp(SystemResp):
    """
    用户登录token
    """
    auth_token: str = Field(default=None, description="登录token")


class CodeResp(SystemResp):
    """
    验证码响应
    """
    code: str = Field(default="", description="验证码")


class LogoutResp(SystemResp):
    """注销响应"""
    pass

class DelHistoryResp(SystemResp):
    """删除历史对话消息"""
    pass
