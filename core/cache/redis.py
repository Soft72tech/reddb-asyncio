from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from redis import asyncio as aioredis
from redis.asyncio.client import Pipeline
from redis.exceptions import ConnectionError

from library.core.abc.cache import AsyncCache, CacheError
from library.core.configs import RedisConfig


class AsyncRedisCache(AsyncCache):
    def __init__(self, config: RedisConfig, **connection_kwargs):
        _connection_kwargs = {"decode_responses": True, "encoding": "utf-8"}
        _connection_kwargs.update(connection_kwargs)

        self.connection_pool: aioredis.ConnectionPool = (
            aioredis.ConnectionPool.from_url(
                url=config.to_string_url(), **_connection_kwargs
            )
        )
        self.config: RedisConfig = config

    async def test_connection(self):
        try:
            connection = self.connection_pool.make_connection()

            await connection.connect()

        except ConnectionError as e:
            raise CacheError(*e.args) from e

        else:
            await connection.disconnect()

    async def shutdown(self):
        await self.connection_pool.disconnect()

    @asynccontextmanager
    async def client(self) -> AsyncGenerator[aioredis.Redis, Any]:
        try:
            yield aioredis.Redis(connection_pool=self.connection_pool)
        except Exception as e:
            raise CacheError(*e.args)

    @asynccontextmanager
    async def pipeline(self, transaction: bool = True) -> AsyncGenerator[Pipeline, Any]:
        async with self.client() as client:
            try:
                yield client.pipeline(transaction=transaction)
            except Exception as e:
                raise CacheError(*e.args)
