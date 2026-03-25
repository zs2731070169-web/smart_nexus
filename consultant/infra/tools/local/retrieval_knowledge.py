import json

import httpx
from agents import function_tool

from config.settings import settings
from infra.logging.logger import log


@function_tool
async def retrieval_knowledge(question: str = "") -> str:
    """
    知识库工具，用于提供电脑、电视、手机等电子设备售后技术咨询
    :param question: 用户咨询的问题
    :return: 检索知识库返回的结果
    """
    try:
        async with httpx.AsyncClient() as client:
            log.info(f"发起HTTP请求，查找知识库")
            response = await client.post(
                url=settings.KNOWLEDGE_BASE_URL,
                json={"question": question},
                timeout=120
            )
            response.raise_for_status()
            result = json.dumps(response.json(), ensure_ascii=False)
            log.info(f"HTTP请求成功，知识库返回结果: {result}")
            return result
    except httpx.HTTPError as e:
        log.error(f"HTTP 请求错误: {e}")
        return json.dumps({
            "status_code": "error",
            "reason": f"HTTP 请求错误: [{type(e).__name__}] {str(e)}",
        }, ensure_ascii=False)
    except Exception as e:
        log.error(f"知识工具执行失败: {e}")
        return json.dumps({
            "status_code": "error",
            "reason": f"知识工具执行失败: [{type(e).__name__}] {str(e)}"
        }, ensure_ascii=False)
