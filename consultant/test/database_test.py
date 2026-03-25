import asyncio

from infra.db.database import get_cursor
from infra.logging.logger import log

if __name__ == '__main__':
    # 简单测试连接池是否正常工作
    async def main():
        try:
            async with get_cursor() as cursor:
                await asyncio.to_thread(cursor.execute, "SELECT 1 AS test")
                result = await asyncio.to_thread(cursor.fetchone)
                log.info(f"数据库连接测试成功，结果: {result}")
        except Exception as e:
            log.error(f"数据库连接测试失败: {e}")


    asyncio.run(main())