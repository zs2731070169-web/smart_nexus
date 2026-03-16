import asyncio
import hashlib
import logging
import time
from typing import Any

import aiofiles
import jieba
from config.settings import settings
from langchain_core.documents import Document
from repo.vector_repo import VectorRepository
from service.ingestion.ingestion_service import IngestionProcessor
from sklearn.metrics.pairwise import cosine_similarity
from starlette.concurrency import run_in_threadpool
from utils.file_utils import FileUtils

# 日志打印
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RetrievalService:

    def __init__(self):
        self.vector_repository = VectorRepository()
        self.ingestion_processor = IngestionProcessor()


    async def retrieval(self, query: str, top_k: int = None) -> list[Document]:
        """
        根据查询语句检索相关文档
        :param top_k:
        :param query: 查询语句
        :return: 相关文档列表
        """

        logger.info(f"[检索流程] 开始执行检索，用户查询：{query}")
        total_start = time.perf_counter()

        # 1+2. 并行执行两路检索
        parallel_start = time.perf_counter()
        results = await asyncio.gather(
            self._retrieval_by_vector(query), # 1. 第一路检索, 使用L2对query进行语义相似度匹配
            self._retrieval_by_title(query) # 2. 第二路检索，使用title和query进行关键词匹配，并得到筛选后的title所对应的文档，对于筛选后的长文本则重新召回精确片段
        )
        parallel_elapsed = time.perf_counter() - parallel_start
        logger.info(f"[检索流程] 两路并行检索完成，耗时：{parallel_elapsed:.2f}秒，一路结果：{len(results[0])}条，二路结果：{len(results[1])}条")

        # 3. 合并两路检索结果
        merge_candidates = results[0] + results[1]
        logger.info(f"[检索流程] 合并后候选文档数：{len(merge_candidates)}")

        # 4. 对检索结果去重，一路检索和二路检索的重复文档记录进行去重
        dedup_start = time.perf_counter()
        unique_candidates = self._deduplicate(merge_candidates)
        dedup_elapsed = time.perf_counter() - dedup_start
        logger.info(f"[检索流程] 去重完成，耗时：{dedup_elapsed:.2f}秒，去重后文档数：{len(unique_candidates)}（去除{len(merge_candidates) - len(unique_candidates)}条重复）")

        # 5. 对去重后的结果进行排序
        rerank_start = time.perf_counter()
        reranked_candidates = self._rerank(unique_candidates, query, top_k)
        rerank_elapsed = time.perf_counter() - rerank_start
        logger.info(f"[检索流程] 重排序完成，耗时：{rerank_elapsed:.2f}秒，最终文档数：{len(reranked_candidates)}")

        total_elapsed = time.perf_counter() - total_start
        logger.info(f"[检索流程] 检索完成，总耗时：{total_elapsed:.2f}秒，用户查询：{query}")

        # 6. 返回最终结果
        return reranked_candidates


    async def _retrieval_by_vector(self, query: str) -> list[Document]:
        """
        根据用户查询到向量库中进行相似性检索,返回整个文档或文档块列表（使用的是L2范数计算相似度得分）
        :param query:
        :return:
        """
        return  await run_in_threadpool(self.vector_repository.query_with_similarity, query, 5)


    async def _retrieval_by_title(self, query: str) -> list[Document]:
        """
        根据用户问题使用文档标题进行关键词匹配和相似性匹配，得到筛选并排序后的文档标题，再通过文档标题返回目标文档内容
        如果是长文本，再进一步对文档内容分片，使用用户查询更进一步召回前top3个文档分片
        最后一起返回一个包含文档内容和元信息的文档列表
        :param query:
        :return:
        """

        if not query or not query.strip():
            logger.warning("查询语句为空，无法进行粗排")
            return []

        # 获取原始文档列表的元信息（文档名、文档路径）
        file_metadata_list = FileUtils.list_file_metadata(settings.CRAWL_OUTPUT_DIR)

        if not file_metadata_list:
            logger.warning("没有找到任何文档元信息，无法进行粗排")
            return []

        # 英文字母转小写
        query = query.lower()

        # 使用文档标题和用户查询进行关键词匹配，得到候选文档元数据（标题）
        candidates_metadata_list = self._search_metadata_by_keyword(query, file_metadata_list)

        # 使用候选文档元数据的标题进行相似性匹配，进一步得到更精确的候选文档元数据（标题）
        fine_candidates_metadata_list = self._search_metadata_by_similarity(query, candidates_metadata_list)

        # 遍历筛选后的文档元数据，获取对应的文档内容，构建document列表，当小于阈值的时候返回完整文档，否则拆分成分片后返回和用户查询最相似的3个文档片段
        expect_documents = []
        for candidate in fine_candidates_metadata_list:
            path = candidate.get('file_path') or ''
            title = candidate.get('title') or ''

            if not path or not title:
                logger.warning(f"文档路径或标题缺失，跳过: {candidate}")
                continue

            content = ""

            try:
                # 读取目标候选文档的内容
                async with aiofiles.open(path, 'r', encoding='utf-8') as f:
                    content = await f.read()
            except Exception as e:
                logger.warning(f"读取文档内容失败，跳过: {path}, \n原因: {str(e)}")
                continue

            if not content:
                logger.warning(f"文档内容为空，跳过: {path}")
                continue

            # 构建document对象
            if len(content) <= settings.CHUNK_SIZE:
                expect_documents.append(
                    Document(
                        page_content=content,
                        metadata= {
                            'path': path,
                            'title': title,
                        }
                    )
                )
            else:
                # 使用用户查询对长文本进行分片并重新召回，返回documents列表
                document_list = self._retrieval_long_content_split_by_similarity(content, query, path, title)
                expect_documents.extend(document_list)

        return expect_documents


    def _deduplicate(self, merge_candidates: list[Document]) -> list[Document]:
        """
        对合并后的文档进行去重，去重的方式可以是根据文档标题+内容前100个字符内容的哈希值进行去重
        :param merge_candidates:
        :return:
        """
        unique_candidates = []
        unique_keys = set()
        for candidate in merge_candidates:
            # 标题 + 文档内容前100个字符 作为计算hash的key
            key = (candidate.metadata.get('title') or '') + (candidate.page_content[:100] or '')
            # hash作为文档是否重复的判断标准
            md5_hash = hashlib.md5(key.encode('utf-8')).hexdigest()
            # 如果没有重复，才添加进去唯一候选文档列表
            if md5_hash not in unique_keys:
                unique_keys.add(md5_hash)
                unique_candidates.append(candidate)
        return unique_candidates


    def _rerank(self, unique_candidates: list[Document], query: str, top_k: int) -> list[Document]:
        """
        对去重后的文档内容根据得分进行重排序
        如果是长文本分片的document，直接添加到分数列表
        如果是短文本分片和相似度检索返回的document，就根据用户查询和文档内容进行相似性计算，计算得分后添加到分数列表
        把分数列表进行排序后返回前2个document作为最终结果
        :param top_k:
        :param unique_candidates:
        :param query:
        :return:
        """

        if not query:
            logger.warning("查询语句为空，无法进行重排序，直接返回候选列表")
            return unique_candidates

        if not unique_candidates:
            logger.warning("候选文档列表为空，无法进行重排序，直接返回空列表")
            return []

        score_rerank_list: list[tuple[float, Document]] = []
        calculate_score_list: list[Document] = []

        DYNAMIC_THRESHOLD = 0.5

        # 遍历去重后的候选文档列表，如果是长文本分片就直接添加到分数排序列表，如果不是就添加到重计算分数列表
        for index, document in enumerate(unique_candidates):
            if document.metadata.get('chunk_index') is not None and document.metadata.get('score') is not None:
                # (score, document)
                score_rerank_list.append((document.metadata['score'], document))
            else:
                # (index, document)
                calculate_score_list.append(document)

        # 对需要重新计算分数的文档列表，使用用户查询和文档内容进行相似性计算，得到新的分数后添加到分数排序列表
        if calculate_score_list:
            # 计算query的向量
            query_embeddings = self.vector_repository.embed_query(query)

            # 从calculate_score_list中得到page_content文本
            contents = [document.page_content for document in calculate_score_list]

            # 对每个content进行向量化
            content_embeddings = self.vector_repository.embed_documents(contents)

            if query_embeddings and content_embeddings:
                # 用户查询和所有content计算余弦相似度得分
                similarity_scores = cosine_similarity([query_embeddings], content_embeddings).flatten()

                # 把分数和对应的文档添加到分数排序列表
                score_rerank_list.extend([
                        (similarity_scores[index], document)
                        for index, document in enumerate(calculate_score_list)
                    ]
                )
            else:
                logger.warning("向量化失败，无法计算余弦相似度，使用默认分数0")
                score_rerank_list.extend([(0.0, document) for document in calculate_score_list])

        # 对分数列表重排序
        reranked_documents = sorted(score_rerank_list, key=lambda x: x[0], reverse=True)

        # 根据阈值或指定的top_k返回最高分的文档列表
        filtered_documents = [
            document for score, document in reranked_documents
            if top_k or score >= DYNAMIC_THRESHOLD
        ]
        return filtered_documents[:top_k] if top_k else filtered_documents


    def _search_metadata_by_keyword(self, query: str, file_metadata_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        对用户问题和文档标题进行关键词匹配，计算相似度得分，返回排序后的文档元数据
        :param query:
        :param file_metadata_list:
        :return: list[dict[str, Any]]:
        """

        SCORE_WEIGHT = 0.7

        # 从列表中过滤掉title为空的file_metadata
        file_metadata_list = [
            meta for meta in file_metadata_list
            if meta.get('title') and meta['title'].strip()
        ]

        for file_metadata in file_metadata_list:
            title = file_metadata['title']

            # 标题转小写
            title = title.lower()

            # 拆分为字符集
            title_char_set = set(title)
            query_char_set = set(query)

            # 使用字符的 交集个数 / 并集个数 计算相似度得分
            score_by_char = len(title_char_set & query_char_set) / len(title_char_set | query_char_set)

            # 拆分为词项集合
            title_term_list = set(jieba.lcut(title, cut_all=True))
            query_term_list = set(jieba.lcut(query, cut_all=True))

            # 使用词项的 交集个数 / 并集个数 计算相似度得分
            score_by_term = len(title_term_list & query_term_list) / len(title_term_list | query_term_list)

            file_metadata['keyword_score'] = SCORE_WEIGHT * score_by_term + (1 - SCORE_WEIGHT) * score_by_char

        return sorted(file_metadata_list, key=lambda x: x['keyword_score'], reverse=True)[:20]


    def _search_metadata_by_similarity(self, query, candidates_metadata_list) -> list[dict[str, Any]]:
        """
        使用用户查询和候选文档元数据列表里的标题进行相似度匹配，筛选出更加精确的排序后的文档元数据
        :param query:
        :param candidates_metadata_list:
        :return:
        """
        SCORE_WEIGHT = 0.7

        # 用户查询嵌入
        query_embeddings = self.vector_repository.embed_query(query)

        # 候选元数据标题列表
        candidate_title_list = [candidates_metadata['title'] for candidates_metadata in candidates_metadata_list]

        # 候选文档元数据标题嵌入
        candidate_title_embeddings = self.vector_repository.embed_documents(candidate_title_list)

        # 向量化失败时，按关键词得分降级返回
        if not query_embeddings or not candidate_title_embeddings:
            logger.warning("向量化失败，跳过相似度匹配，按关键词得分返回")
            return sorted(candidates_metadata_list, key=lambda x: x.get('keyword_score', 0), reverse=True)[:5]

        # 进行余弦相似性匹配，得到匹配得分
        similarity_scores = cosine_similarity([query_embeddings], candidate_title_embeddings).flatten()

        # 把相似性得分和关键词得分一起进行加权求和，然后把计算的分数添加到候选文档中
        for i, candidate_metadata in enumerate(candidates_metadata_list):
            keyword_score = candidate_metadata['keyword_score']
            similarity_score = similarity_scores[i]

            # 当相似性分数<0，就赋值为0
            if similarity_scores[i] < 0:
                similarity_score = 0

            # 两则得分加权求和并复制到候选文档元数据
            candidate_metadata['similarity_score'] = SCORE_WEIGHT * similarity_score + (1 - SCORE_WEIGHT) * keyword_score

        # 得到5个进一步筛选的候选文档元数据
        return sorted(candidates_metadata_list, key=lambda x: x['similarity_score'], reverse=True)[:5]


    def _retrieval_long_content_split_by_similarity(self, content: str, query: str, path: str, title: str) -> list[Document]:
        """
        根据用户问题，从候选文档的内容分片里进行相似度匹配，并返回最相似的前3个document对象
        :param content:
        :param query:
        :param path:
        :param title:
        :return:
        """
        # 拆分文档
        chunks = self.ingestion_processor.spliter.split_text(content)

        # 分片注入文档标题
        chunks_with_title = [f"主题：{title}\n\n内容：{chunk}" for chunk in chunks]

        # 向量化查询
        query_embeddings = self.vector_repository.embed_query(query)
        if not query_embeddings:
            logger.warning(f"查询向量化失败，无法执行长文本分片召回: {title}")
            return []

        # 向量化分片文档
        chunk_embeddings = self.vector_repository.embed_documents(chunks_with_title)
        if not chunk_embeddings:
            logger.warning(f"分片向量化失败，无法执行长文本分片召回: {title}")
            return []

        # 计算相似度
        scores = cosine_similarity([query_embeddings], chunk_embeddings).flatten()

        # 获取最相似的前3个得分的索引
        top_score_indexes = scores.argsort()[-3:][::-1]

        top_candidates = []
        for top_score_index in top_score_indexes:
            document = Document(
                page_content=chunks_with_title[top_score_index],
                metadata= {
                    'title': title,
                    'path': path,
                    'chunk_index': int(top_score_index),
                    'score': float(scores[top_score_index]),
                }
            )
            top_candidates.append(document)

        return top_candidates
