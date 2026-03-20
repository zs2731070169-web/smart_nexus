import asyncio
from contextlib import asynccontextmanager

import pymysql
from dbutils.pooled_db import PooledDB
from pymysql.cursors import DictCursor

from config.settings import settings
from infra.logging.logger import log

# 全局连接池（模块加载时初始化，整个应用生命周期内复用）
_pool = PooledDB(
    creator=pymysql,  # 使用 pymysql 作为数据库驱动
    maxconnections=settings.MYSQL_MAX_CONNECTIONS,  # 最大连接数
    mincached=1,  # 初始化时池中至少创建的空闲连接数
    maxcached=3,  # 池中最多的空闲连接数
    blocking=True,  # 连接数耗尽时阻塞等待，而非抛出异常
    host=settings.MYSQL_HOST,
    port=settings.MYSQL_PORT,
    user=settings.MYSQL_USER,
    password=settings.MYSQL_PASSWORD,
    database=settings.MYSQL_DATABASE,
    charset=settings.MYSQL_CHARSET,
    connect_timeout=settings.MYSQL_CONNECT_TIMEOUT,
    cursorclass=DictCursor  # 默认返回字典格式的查询结果
)


# 使 get_cursor() 可配合 with 语句使用，自动管理生命周期
@asynccontextmanager
async def get_cursor():
    """
    从连接池中获取一个数据库的游标。

    配合 with 语句使用，确保连接自动归还：
    """
    conn = None
    cursor = None
    try:
        # 从连接池中获取连接, 连接获取是阻塞操作，放到线程中执行避免阻塞事件循环
        conn = await asyncio.to_thread(_pool.connection)
        cursor = conn.cursor()
        # 将游标交给调用方，with 块结束后继续执行 commit / finally
        # __enter__：yield 之前的代码
        yield cursor  # ← 使用了@contextmanager，必须有，且只能有一个 yield，作为上下文管理器的核心
        # __exit__：yield 之后的代码，正常执行到这里说明没有异常
    except pymysql.err.OperationalError:
        log.error("无法连接到数据库，请检查数据库配置和状态")
        raise
    finally:
        if cursor:
            # 先关闭游标，释放结果集资源
            cursor.close()
        if conn:
            # 归还连接到连接池，并非真正关闭
            await asyncio.to_thread(conn.rollback)