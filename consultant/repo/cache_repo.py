from infra.db.redis import get_session


class RedisOperation:

    async def save_with_ex(self, key: str, value: str, expires_at: int) -> bool:
        """
        保存key-value到缓存，到期自动删除
        :param key:
        :param value:
        :param expires_at:
        :return:
        """
        async with get_session() as session:
            return await session.set(key, value, expires_at)

    async def get_value(self, key: str) -> str:
        """
        获取key-value
        :param key:
        :return:
        """
        async with get_session() as session:
            return await session.get(key)

    async def delete_value(self, key: str) -> bool:
        """
        删除key
        :param key:
        :return:
        """
        async with get_session() as session:
            return await session.delete(key)

    async def exists_key(self, key: str) -> bool:
        """
        判断key是否存在
        :param key:
        :return:
        """
        async with get_session() as session:
            return await session.exists(key) > 0


redis_operation = RedisOperation()
