import asyncio

from service.retrieval.retrieval_service import RetrievalService
from config.settings import settings
from utils.file_utils import FileUtils


async def main():
    retriever = RetrievalService()
    documents = await retriever.retrieval("windows电脑如何休眠", 1)
    for document in documents:
        print(document)

if __name__ == '__main__':
    asyncio.run(main())