import json
import logging

import requests

from config.settings import settings

# 日志打印
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class KnowledgeCrawler:

    @staticmethod
    def crawl_client(knowledge_no: str) -> dict:
        """
        爬取知识库数据
        :param knowledge_no: 知识库编号
        :return: 爬取结果
        """

        try:
            response = requests.get(
                settings.KNOWLEDGE_BASE_URL + '/api/knowledge/knowledgeDetails',
                params={
                    'knowledgeNo': knowledge_no,
                }
            )
            response.raise_for_status()  # 检查请求是否成功

            content = json.loads(response.content) # 反序列化

            return content.get('data', {})
        except Exception as e:
            logger.error(f"HTTP请求失败: {e}")
            return {}