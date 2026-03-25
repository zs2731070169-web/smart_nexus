from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator


from redis.asyncio import Redis, ConnectionPool
from redis.exceptions import RedisError

from config.settings import settings
from infra.logging.logger import log

# 全局连接池
_pool = ConnectionPool(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    password=settings.REDIS_PASSWORD,
    db=settings.REDIS_DB,
    max_connections=settings.REDIS_MAX_CONNECTIONS,
    decode_responses=True,  # 自动将字节解码为字符串
)


@asynccontextmanager
async def get_session() -> AsyncGenerator[Redis, Any]:
    """
    从连接池中获取一个 Redis 连接。

    async with get_redis() as r:
        await r.set("key", "value")
        value = await r.get("key")
    """
    client = Redis(connection_pool=_pool)
    log.info("从 Redis 连接池获取连接")
    try:
        yield client
    except RedisError:
        log.error("无法连接到 Redis，请检查 Redis 配置和状态")
        raise
    finally:
        # 将连接归还连接池，并非真正关闭
        if client:
            await client.close()
