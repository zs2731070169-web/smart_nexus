import logging

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

from config.settings import settings

# 日志打印
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VectorRepository:

    def __init__(self):
        # embeddings模型的初始化
        self.embeddings = OpenAIEmbeddings(
            model=settings.EMBEDDING_MODEL,
            base_url=settings.BASE_URL,
            api_key=settings.API_KEY
        )

        # Chroma向量数据库的初始化
        self.chroma_client = Chroma(
            collection_name='smart_nexus',
            embedding_function=self.embeddings,
            persist_directory=settings.VECTOR_STORE_PATH
        )

    def save_documents(self, documents: list) -> int:
        """
        保存documents文档到向量数据库(底层自动进行文档嵌入)
        :param documents: 待保存的文档列表
        :return: 成功保存的文档数量
        """
        try:
            if not documents:
                logger.warning("没有需要保存的文档，保存失败")
                return 0
            self.chroma_client.add_documents(documents=documents)
            logger.info(f"已保存 {len(documents)} 条向量数据到向量数据库")
            return len(documents)
        except Exception as e:
            logger.error(f"保存向量数据失败，原因: {str(e)}")
            return 0


    def embed_query(self, query: str) -> list[float]:
        """
        将查询语句转换为向量
        :param query: 查询语句
        :return: 向量表示
        """
        try:
            query_vector = self.embeddings.embed_query(query)
            logger.info(f"查询语句已成功转换为向量")
            return query_vector
        except Exception as e:
            logger.error(f"查询语句转换为向量失败，原因: {str(e)}")
            return []


    def embed_documents(self, documents: list[str]) -> list[list[float]]:
        """
        将文档转为向量
        :param documents:
        :return:
        """
        try:
            if not documents:
                logger.warning("没有需要转换的文档，转换失败")
                return []
            document_vectors = self.embeddings.embed_documents(texts=documents)
            logger.info(f"已成功将 {len(document_vectors)} 条文档转换为向量")
            return document_vectors
        except Exception as e:
            logger.error(f"文档转换为向量失败，原因: {str(e)}")
            return []


    def query_with_similarity(self, query: str, top_k: int = 5) -> list[Document]:
        """
        使用相似度搜索查询向量数据库
        :param query: 查询语句
        :param top_k: 返回的相似文档数量
        :return: 相似文档列表
        """
        try:
            results = self.chroma_client.similarity_search(query=query, k=top_k)
            logger.info(f"已成功执行相似度搜索，返回 {len(results)} 条结果")
            return results
        except Exception as e:
            logger.error(f"相似度搜索失败，原因: {str(e)}")
            return []