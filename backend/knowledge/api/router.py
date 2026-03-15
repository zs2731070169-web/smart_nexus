import logging
import os
import time
import uuid

import aiofiles

# 日志打印
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from pathlib import Path
from fastapi import APIRouter, UploadFile, File
from starlette.concurrency import run_in_threadpool

from api.schema import UploadedFileResponse
from api.schema import QueryResponse
from api.schema import QueryRequest
from config.settings import settings
from service.ingestion.ingestion_service import IngestionProcessor
from service.retrieval.query_service import QueryService
from service.retrieval.retrieval_service import RetrievalService

router = APIRouter()

processor = IngestionProcessor()
retriever = RetrievalService()
query_service = QueryService()

@router.post("/injection/upload", response_model=UploadedFileResponse, summary="上传知识库")
async def upload_file(file: UploadFile = File(...)):
    tmp_file_path = None
    try:
        if not file.filename:
            logger.error("上传文件必须包含文件名")
            return UploadedFileResponse(
                status = "400",
                description = "上传知识库失败, 文件必须包含文件名",
                filename = file.filename
            )

        # 获取文件后缀
        file_suffix = os.path.splitext(file.filename.strip())[1] if file.filename.strip() else ""
        if not file_suffix:
            logger.error("文件名必须包含后缀，例如 .md")
            return UploadedFileResponse(
                status = "500",
                description = "上传知识库失败, 文件名必须包含后缀，例如 .md",
                filename = file.filename
            )

        # 校验文件类型
        ALLOWED_EXTENSIONS = {".md", ".txt"}
        if file_suffix.lower() not in ALLOWED_EXTENSIONS:
            logger.error(f"不支持的文件格式: {file_suffix}")
            return UploadedFileResponse(
                status = "400",
                description = f"不支持的文件格式: {file_suffix}，仅支持 {', '.join(ALLOWED_EXTENSIONS)}",
                filename = file.filename
            )

        tmp_dir = Path(settings.TMP_OUTPUT_DIR)  # 临时存储文件

        # 如果临时目录不存在则新建
        if not tmp_dir.exists():
            tmp_dir.mkdir(parents=True, exist_ok=True)

        # 使用 uuid 前缀 + 原始文件名构建临时路径，确保 extract_filename 能提取有意义的标题
        safe_filename = f"{uuid.uuid4().hex}_{file.filename.strip()}"
        tmp_file_path = os.path.join(str(tmp_dir), safe_filename)

        async with aiofiles.open(tmp_file_path, "wb") as tmp:
            # 分批次读取,每次读取1M
            while file_content := await file.read(1024*1024):
                await tmp.write(file_content)

        logger.info(f"文件临时保存成功，路径: {tmp_file_path}")

        # 添加到向量库
        saved_chunks = await run_in_threadpool(processor.batch_ingestion, [tmp_file_path])
        if not saved_chunks:
            logger.error("知识库上传失败，未保存任何数据到向量数据库")
            return UploadedFileResponse(
                status = "500",
                description="知识库上传失败",
                filename = file.filename
            )
        else:
            logger.info(f"上传知识库成功，文件名：{file.filename}, 保存块数：{saved_chunks}")
            return UploadedFileResponse(
                filename = file.filename,
                chunk_size = saved_chunks
            )
    except Exception as e:
        logger.error(f"上传知识库失败，原因: {str(e)}")
        return UploadedFileResponse(
            status = "500",
            description=f"上传知识库失败, 服务器异常",
            filename=file.filename
        )
    finally:
        # 清除临时文件路径
        if tmp_file_path and os.path.exists(tmp_file_path):
            try:
                os.remove(tmp_file_path)
            except Exception as e:
                logger.error(f"删除临时文件失败，路径: {tmp_file_path}, 原因: {str(e)}")


@router.post("/retrieval/query", response_model=QueryResponse, summary="检索知识库")
async def query(query: QueryRequest):
    try:
        total_start = time.perf_counter()
        question = query.question
        if not question or not question.strip():
            logger.error(f"无法获取查询参数query: {query}")
            return QueryResponse(status="400", description="查询参数不能为空")

        logger.info(f"[查询接口] 收到查询请求，问题：{question}, top_k：{query.top_k}")

        # 知识检索
        retrieval_start = time.perf_counter()
        documents =  await retriever.retrieval(question, query.top_k)
        retrieval_elapsed = time.perf_counter() - retrieval_start
        logger.info(f"[查询接口] 知识检索完成，耗时：{retrieval_elapsed:.2f}秒，返回文档数：{len(documents)}")

        # 模型生成回复
        llm_start = time.perf_counter()
        content = await run_in_threadpool(query_service.query, question, documents)
        llm_elapsed = time.perf_counter() - llm_start
        logger.info(f"[查询接口] 模型生成回复完成，耗时：{llm_elapsed:.2f}秒")

        total_elapsed = time.perf_counter() - total_start
        logger.info(f"[查询接口] 请求处理完成，总耗时：{total_elapsed:.2f}秒 (检索：{retrieval_elapsed:.2f}秒 + 模型：{llm_elapsed:.2f}秒)")

        return QueryResponse(content=content)
    except Exception as e:
        logger.error(f"查询失败，原因: {str(e)}")
        return QueryResponse(status="500", description="查询异常")
