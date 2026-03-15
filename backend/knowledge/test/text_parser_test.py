from service.crawler.http_client_service import KnowledgeCrawler

from service.crawler.text_parser_service import Parser

content = KnowledgeCrawler.crawl_client(knowledge_no="11")
parser = Parser()
markdown = parser.parser_to_md(content, "11")
print(markdown)