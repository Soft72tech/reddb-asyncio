import datetime
from enum import Enum
from typing import Any, AsyncGenerator, Generator, Optional, Type, TypeAlias, cast
from uuid import UUID

from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.engine import Connection as Connection
from sqlalchemy.engine import Dialect
from sqlalchemy.engine import Engine as Engine
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.orm import Session as Session
from sqlalchemy.orm.session import sessionmaker
from sqlalchemy.types import BINARY, CHAR, String, TypeDecorator

SessionContext: TypeAlias = Generator[Session, None, None]
SessionMaker: TypeAlias = sessionmaker
ConnectionContext: TypeAlias = Generator[Connection, None, None]

AsyncEngine: TypeAlias = AsyncEngine
AsyncConnection: TypeAlias = AsyncConnection
AsyncSession: TypeAlias = AsyncSession
AsyncSessionContext: TypeAlias = AsyncGenerator[AsyncSession, None]
AsyncSessionMaker: TypeAlias = async_sessionmaker[AsyncSession]
AsyncConnectionContext: TypeAlias = AsyncGenerator[AsyncConnection, None]


class DateTimeUTC(TypeDecorator[datetime.datetime]):
    """Timezone Aware DateTime.

    Ensure UTC is stored in the database and that TZ aware dates are returned for all dialects.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    @property
    def python_type(self) -> Type[datetime.datetime]:
        return datetime.datetime

    def process_bind_param(
        self, value: Optional[datetime.datetime], dialect: Dialect
    ) -> Optional[datetime.datetime]:
        # print("PROCESS BIND", value, type(value))

        if value is None:
            return value
        if not value.tzinfo:
            msg = "tzinfo is required"
            raise TypeError(msg)
        return value.astimezone(datetime.timezone.utc)

    def process_result_value(
        self, value: Optional[datetime.datetime], dialect: Dialect
    ) -> Optional[datetime.datetime]:
        # print("PROCESS RESULT", value, type(value))

        if value is None:
            return value
        if value.tzinfo is None:
            return value.replace(tzinfo=datetime.timezone.utc)
        return value


class GUID(TypeDecorator[UUID]):
    """Platform-independent GUID type.

    Uses PostgreSQL's UUID type (Postgres, DuckDB, Cockroach),
    otherwise uses BINARY(16) or CHAR(32),
    storing as stringified hex values.

    Will accept stringified UUIDs as a hexstring or an actual UUID

    """

    impl = BINARY(16)
    cache_ok = True

    @property
    def python_type(self) -> Type[UUID]:
        return UUID

    def __init__(self, *args: Any, binary: bool = True, **kwargs: Any) -> None:
        self.binary = binary

    def load_dialect_impl(self, dialect: Dialect) -> Any:
        if dialect.name in {"postgresql", "duckdb"}:
            return dialect.type_descriptor(PG_UUID())

        if self.binary:
            return dialect.type_descriptor(BINARY(16))

        return dialect.type_descriptor(CHAR(32))

    def process_bind_param(
        self,
        value: Optional[bytes | str | UUID],
        dialect: Dialect,
    ) -> Optional[bytes | str]:
        if value is None:
            return value

        if dialect.name in {"postgresql", "duckdb"}:
            return str(value)

        if (value := self.to_uuid(value)) is None:
            return value

        return value.bytes if self.binary else value.hex

    def process_result_value(
        self,
        value: Optional[bytes | str | UUID],
        dialect: Dialect,
    ) -> Optional[UUID]:
        if value is None:
            return value

        if value.__class__.__name__ == "UUID":
            return cast("UUID", value)

        if self.binary:
            return UUID(bytes=cast("bytes", value))

        return UUID(hex=cast("str", value))

    @staticmethod
    def to_uuid(value: Any) -> Optional[UUID]:
        if value.__class__.__name__ == "UUID" or value is None:
            return cast("UUID | None", value)

        try:
            value = UUID(hex=value)

        except (TypeError, ValueError):
            value = UUID(bytes=value)

        return cast("UUID | None", value)

    def compare_values(self, x: Any, y: Any) -> bool:
        """Compare two values for equality."""
        if x.__class__.__name__ == "UUID" and y.__class__.__name__ == "UUID":
            return cast("bool", x.bytes == y.bytes)

        return cast("bool", x == y)


class StringEnum(TypeDecorator[Enum]):
    impl = String
    cache_ok = True

    @property
    def python_type(self) -> Type[Enum]:
        return Enum

    def __init__(self, enum_type: Type[Enum], *args: Any, **kwargs: Any):
        self._enum_type = enum_type

    def process_bind_param(
        self, value: Optional[Enum | str | int], dialect: Dialect
    ) -> Optional[Enum]:
        if value is None:
            return value

        if isinstance(value, str):
            return value

        if isinstance(value, int):
            return self._enum_type(value).name

        return value.name

    def process_result_value(self, value: Optional[Enum]) -> Optional[Enum]:
        if value is None:
            return value

        if isinstance(value, Enum):
            return value

        if isinstance(value, str):
            return self._enum_type[value]

        if isinstance(value, int):
            return self._enum_type(value)
