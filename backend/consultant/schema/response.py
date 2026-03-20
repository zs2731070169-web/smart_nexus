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

    finished_reason: Optional[FinishedReason] = Field(default=None, description="agent结束原因，NORMAL/EXCEPTION/MAX_TOKEN")

    error_message: Optional[str] = Field(default=None,
                                         description="如果stop_reason是EXCEPTION，这里会有错误信息；否则为空字符串")


class StreamMessages(BaseModel):
    """流式输出的数据对象"""
    id: str = Field(description="流式输出的数据对象id")

    data: Union[DeltaMessage, FinishMessage] = Field(description="流式输出的数据对象，包含分片消息和结束消息两种类型")

    status: StreamStatus = Field(description="流式状态，控制SSE生命周期，PROCESSING/FINISHED")

    metadata: Metadata = Field(description="流式输出数据对象的元数据")


def build_processing_stream_messages(data: str, render_type: RenderType) -> StreamMessages:
    """构建正在处理过程中的流式消息"""
    if not isinstance(data, str):
        raise TypeError("返回数据必须是字符串")

    if not isinstance(render_type, RenderType):
        raise TypeError("渲染类型必须是RenderType对象和")

    return StreamMessages(
        id=str(uuid.uuid4().hex),
        data=DeltaMessage(data=data, render_type=render_type),  # 返回正在流式输出的分片消息
        status=StreamStatus.PROCESSING,
        metadata=Metadata(create_time=str(datetime.now()))
    )


def build_finished_stream_messages(message_id: Optional[str]) -> StreamMessages:
    """构建完成时的流式消息"""
    if message_id and not isinstance(message_id, str):
        raise TypeError("消息id必须是字符串")

    if message_id is None:
        message_id = str(uuid.uuid4().hex)

    return StreamMessages(
        id=message_id,
        data=FinishMessage(),  # 返回结束消息
        status=StreamStatus.FINISHED,
        metadata=Metadata(create_time=str(datetime.now()))
    )
