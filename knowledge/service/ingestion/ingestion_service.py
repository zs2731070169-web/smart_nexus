import logging

from utils.file_utils import FileUtils

# 日志打印
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores.utils import filter_complex_metadata
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from repo.vector_repo import VectorRepository
from config.settings import settings


class IngestionProcessor:


    def __init__(self):
        self.vector_repository = VectorRepository()
        self.spliter = RecursiveCharacterTextSplitter(
            # 先按照md文档的每个二级标题切分，如果依然很大就是用段落里的加粗符号切分...
            separators=["\n##", "\n**", "\n\n", "\n", " ", ""],
            keep_separator=False,
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
        )


    def batch_ingestion(self, document_paths: list[str]) -> int:
        """
        批量动态摄入文档到向量库
        :param document_paths: 文档路径列表
        :param batch_size: 每批次处理的文档数量
        :return: 成功保存的文档块总数
        """
        try:
            if not document_paths:
                logger.error(f"文档路径列表为空")
                return 0

            if not isinstance(document_paths, list):
                logger.error(f"文档路径列表必须是一个list")
                return 0

            # 加载一批文档
            batch_documents = []
            for path in document_paths:
                documents = TextLoader(path, encoding="utf-8").load()
                batch_documents.extend(documents)
            logger.info(f"成功加载{len(batch_documents)}个原始文档")

            # 过滤掉内容为空的文档
            documents = [doc for doc in batch_documents if doc.page_content]

            if not documents:
                logger.warning("没有加载到任何文档，摄入失败")
                return 0

            # 对文档进行分块处理，生成新的文档列表
            processed_docs = []
            for document in documents:
                # 获取文档来源信息
                path = document.metadata.get("source", "")
                filename = FileUtils.extract_filename(path)

                # 元数据添加title
                document.metadata['title'] = filename

                if len(document.page_content) > settings.CHUNK_SIZE:
                    # 文档超过阈值，进行分块
                    chunks = self.spliter.split_text(document.page_content)

                    if not chunks:
                        logger.warning(f"文档分块结果为空，跳过: {path}")
                        continue

                    # 为每个分块创建新的 Document 对象，保留原始元数据
                    for i, chunk_text in enumerate(chunks):
                        chunk_doc = Document(
                            page_content=f"主题：{filename}\n\n内容：{chunk_text}",
                            metadata={**document.metadata, "chunk_index": i},
                        )
                        processed_docs.append(chunk_doc)
                    logger.info(f"\n文档 {filename} 分块为 {len(chunks)} 个片段")
                else:
                    processed_docs.append(document) # 小文档不需要分块，直接添加

            if not processed_docs:
                logger.warning("处理后没有可用文档，摄入失败")
                return 0

            # 过滤元数据
            clean_documents = filter_complex_metadata(processed_docs)

            # 存储文档
            return self.vector_repository.save_documents(clean_documents)
        except Exception as e:
            logger.error(f"文档摄入失败，原因: {str(e)}")
            return 0


