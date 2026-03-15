import logging
import os
import time

from service.crawler.http_client_service import KnowledgeCrawler
from service.crawler.text_parser_service import Parser
from utils.text_utils import TextUtils
from config.settings import settings
from utils.file_utils import FileUtils

# 日志打印
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Crawler:

    def crawl(self):
        """
        批量爬取1000条知识库数据，并转换为Markdown格式，保存到本地
        :return:
        """
        parser = Parser()

        for i in range(1313, 1337):
            # 爬取数据
            content = KnowledgeCrawler.crawl_client(knowledge_no=str(i))

            # 文件不存在就跳过
            if not content:
                logger.warning(f"第 {i} 个文件爬取失败，内容为空，暂停爬取，等待3秒后再次尝试...")
                time.sleep(3)
                continue

            # 标题不存在就跳过
            if not content.get('title'):
                continue

            # 转为markdown格式
            markdown = parser.parser_to_md(content, str(i))

            # 去除文件名里的特殊字符
            clean_title = TextUtils.clean_filename(content.get('title'))
            # 裁剪文件名
            clean_title = clean_title[:50].rstrip("_") if len(clean_title) > 50 else clean_title
            # 拼接文件名
            filename = f"{i:04d}_{clean_title}.md"

            # 输出目录
            dir_path = settings.CRAWL_OUTPUT_DIR

            # 保存到指定目录
            result = FileUtils.save_as_file(dir_path, filename, markdown)
            if result:
                logger.info(f"第 {i} 个文件成功保存: {os.path.join(dir_path, filename)}")
            else:
                logger.warning(f"第 {i} 个文件保存失败: {os.path.join(dir_path, filename)}")

            # 睡眠0.2秒，避免请求压力过大
            time.sleep(0.2)


if __name__ == '__main__':
    crawler = Crawler()
    crawler.crawl()