import json
import logging
import time

import requests

from config.settings import settings

# 日志打印
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class KnowledgeCrawler:

    @staticmethod
    def crawl_client(knowledge_no: str, max_retries: int = 3) -> dict:
        """
        爬取知识库数据，连接异常时自动重试（指数退避）
        :param knowledge_no: 知识库编号
        :param max_retries: 最大重试次数
        :return: 爬取结果，失败返回 {}
        """
        url = settings.KNOWLEDGE_BASE_URL + '/api/knowledge/knowledgeDetails'
        for attempt in range(max_retries + 1):
            try:
                response = requests.get(url, params={'knowledgeNo': knowledge_no}, timeout=15)
                response.raise_for_status()
                content = json.loads(response.content)
                return content.get('data', {})
            except (requests.ConnectionError, requests.Timeout) as e:
                # 连接被断开或超时：重试，指数退避 5s/15s/45s
                if attempt < max_retries:
                    wait = 5 * (3 ** attempt)
                    logger.warning(f"连接异常（第 {attempt + 1} 次），{wait}s 后重试: {e}")
                    time.sleep(wait)
                else:
                    logger.error(f"连接异常，已达最大重试次数，跳过 {knowledge_no}: {e}")
                    return {}
            except Exception as e:
                # 其他错误（HTTP 错误、JSON 解析失败等）不重试
                logger.error(f"HTTP请求失败: {e}")
                return {}