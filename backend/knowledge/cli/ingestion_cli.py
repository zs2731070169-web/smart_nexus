import logging
import math

from config.settings import settings
from service.ingestion.ingestion_service import IngestionProcessor
from tqdm import tqdm
from utils.file_utils import FileUtils

# 日志打印
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Injector:

    def __init__(self):
        self.processor = IngestionProcessor()
        # 读取所有文件所在路径
        files = FileUtils.list_dir(settings.MD_FOLDER_PATH)
        # 文件去重
        self.clean_files = FileUtils.remove_duplicate_files(files)

    def inject(self):
        """
        建立文档索引，按批次处理文件并上传到向量库
        """
        clean_files = self.clean_files
        if not clean_files:
            logger.warning("没有找到可处理的文件")
            return

        success_chunks = 0
        fail_batches = 0
        batch_size = 20

        # 按 batch_size 分批处理文件，总共执行 total_batches 个批次
        total_batches = math.ceil(len(clean_files) / batch_size)

        with tqdm(total=total_batches, desc="知识库上传进度") as pbar:
            for i in range(0, len(clean_files), batch_size):
                batch_files = clean_files[i: i + batch_size]
                try:
                    saved_chunks = self.processor.batch_ingestion(batch_files)
                    if saved_chunks:
                        success_chunks += saved_chunks
                    else:
                        fail_batches += 1
                except Exception as e:
                    logger.error(f"批次处理失败，原因: {e}")
                    fail_batches += 1
                finally:
                    pbar.update(1)
                    pbar.set_postfix({
                        "成功块数": success_chunks,
                        "失败批次": fail_batches,
                    })


if __name__ == '__main__':
    injector = Injector()
    injector.inject()