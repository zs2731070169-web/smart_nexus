import json

import httpx
from pydantic import BaseModel, Field

from config.settings import settings
from infra.logging.logger import log
from infra.tools.base import BaseTool, ToolResult


class RetrievalKnowledgeArgs(BaseModel):
    question: str = Field(default="", description="用户咨询的问题")


class RetrievalKnowledge(BaseTool):
    name = "retrieval_knowledge"
    description = "知识库工具，用于提供电脑、电视、手机等电子设备售后技术咨询"
    input_model = RetrievalKnowledgeArgs

    async def execute(self, arguments: RetrievalKnowledgeArgs) -> ToolResult:
        try:
            async with httpx.AsyncClient() as client:
                log.info("发起HTTP请求，查找知识库")
                response = await client.post(
                    url=settings.KNOWLEDGE_BASE_URL,
                    json={"question": arguments.question},
                    timeout=120,
                )
                response.raise_for_status()
                output = json.dumps(response.json(), ensure_ascii=False)
                log.info(f"HTTP请求成功，知识库返回结果: {output}")
                return ToolResult(output=output)
        except httpx.HTTPError as e:
            log.error(f"HTTP 请求错误: {e}")
            return ToolResult(
                output=json.dumps({
                    "status_code": "error",
                    "reason": f"HTTP 请求错误: [{type(e).__name__}] {str(e)}",
                }, ensure_ascii=False),
                is_error=True,
            )
        except Exception as e:
            log.error(f"知识工具执行失败: {e}")
            return ToolResult(
                output=json.dumps({
                    "status_code": "error",
                    "reason": f"知识工具执行失败: [{type(e).__name__}] {str(e)}",
                }, ensure_ascii=False),
                is_error=True,
            )


retrieval_knowledge = RetrievalKnowledge()
