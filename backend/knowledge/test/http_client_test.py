from service.crawler.http_client_service import KnowledgeCrawler

html_content = KnowledgeCrawler.crawl_client(knowledge_no="1")
print(html_content)