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
        consecutive_failures = 0  # 连续失败计数，用于判断是否触发反爬限制

        for i in range(0, 2000):
            # 爬取数据
            content = KnowledgeCrawler.crawl_client(knowledge_no=str(i))

            # 文件不存在就直接跳过或等待后跳过
            if not content:
                consecutive_failures += 1
                # 连续失败 5 次触发 60s 长暂停，避免持续请求加重服务端封禁
                if consecutive_failures >= 5:
                    logger.warning(f"连续失败 {consecutive_failures} 次，暂停 60s 等待服务端恢复...")
                    time.sleep(60)
                    consecutive_failures = 0
                else:
                    logger.warning(f"第 {i} 个文件内容为空，跳过")
                # 到达最大重试等待后、当前文档返回为空、系统异常，跳过然后执行下一个文档爬取
                continue

            consecutive_failures = 0  # 成功则重置计数器

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