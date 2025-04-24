from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator


class CacheError(Exception): ...


class AsyncCache(ABC):
    @abstractmethod
    async def test_connection(self): ...

    @abstractmethod
    @asynccontextmanager
    async def client(self) -> AsyncGenerator[Any, Any]:
        yield
