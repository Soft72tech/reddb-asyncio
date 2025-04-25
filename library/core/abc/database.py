from abc import ABC, abstractmethod
from contextlib import asynccontextmanager, contextmanager


class DatabaseError(Exception): ...


class AsyncDatabase(ABC):
    @abstractmethod
    @asynccontextmanager
    async def connection(self) -> "AsyncConnectionContext":
        yield

    @abstractmethod
    async def test_connection(self): ...

    @abstractmethod
    async def shutdown(self): ...

    @abstractmethod
    @asynccontextmanager
    async def session(self) -> "AsyncSessionContext":
        yield

    @abstractmethod
    async def create_user(self): ...

    @abstractmethod
    async def drop_user(self): ...

    @abstractmethod
    async def create_database(self): ...

    @abstractmethod
    async def drop_database(self): ...

    @abstractmethod
    async def usage(self) -> int: ...


class SyncDatabase(ABC):
    @abstractmethod
    @contextmanager
    def connection(self) -> "ConnectionContext": ...

    @abstractmethod
    def test_connection(self): ...

    @abstractmethod
    def shutdown(self): ...

    @abstractmethod
    @contextmanager
    def session(self) -> "SessionContext": ...

    @abstractmethod
    def create_user(self): ...

    @abstractmethod
    def drop_user(self): ...

    @abstractmethod
    def create_database(self): ...

    @abstractmethod
    def drop_database(self): ...

    @abstractmethod
    def usage(self) -> int: ...


from library.core.database.types import (  # noqa: E402
    AsyncConnectionContext,
    AsyncSessionContext,
    ConnectionContext,
    SessionContext,
)
