from pydantic import BaseModel, Field


class UploadedFileResponse(BaseModel):
    status: str = Field(default="200", description="执行状态码")
    description: str = Field(default="ok", description="执行描述信息")
    filename: str = Field(default="", description="上传的文件名")
    chunk_size: int = Field(default=0, description="保存文件的分片数量")


class QueryResponse(BaseModel):
    status: str = Field(default="200", description="执行状态码")
    description: str = Field(default="ok", description="执行描述信息")
    content: str = Field(default="", description="查询结果")


class QueryRequest(BaseModel):
    question: str = Field(default="", description="查询问题")
    top_k: int = Field(default=0, description="返回条数")