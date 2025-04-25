from enum import Enum

from library.core.cache.redis import AsyncRedisCache
from library.core.configs import RedisConfig


class MessageBusTicket(Enum): ...


class MessageBusCosumer(Enum): ...


class AsyncRedisMessageBus(AsyncRedisCache):
    def __init__(self, config: RedisConfig, **connection_kwargs):
        super().__init__(config, **connection_kwargs)

    def select(self, key: MessageBusTicket, consumer_group: MessageBusCosumer): ...

    async def write(self): ...

    async def read(self): ...

    async def remove(self): ...

    async def len(self): ...

    async def pending(self): ...
