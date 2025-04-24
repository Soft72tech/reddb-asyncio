from contextlib import AsyncExitStack, asynccontextmanager, contextmanager
from typing import Optional

import sqlalchemy as sa
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, quoted_name
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import sessionmaker

from library.core.abc.database import AsyncDatabase, DatabaseError, SyncDatabase
from library.core.configs import PostgresConfig
from library.core.database.types import (
    AsyncConnection,
    AsyncConnectionContext,
    AsyncEngine,
    AsyncSessionContext,
    AsyncSessionMaker,
    ConnectionContext,
    Engine,
    SessionContext,
    SessionMaker,
)


class AsyncPostgresDatabase(AsyncDatabase):
    def __init__(self, config: PostgresConfig, **connection_kwargs):
        _connection_kwargs = {
            "pool_size": 100,
            # "poolclass": NullPool,
            "connect_args": {"options": "-c timezone=utc"},
        }
        _connection_kwargs.update(connection_kwargs)

        self.engine: AsyncEngine = create_async_engine(
            config.to_string_url(), **_connection_kwargs
        )

        self.sessionmaker: AsyncSessionMaker = async_sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )

        self.config: PostgresConfig = config

    @asynccontextmanager
    async def connection(self) -> AsyncConnectionContext:
        async with self.engine.connect() as connection:
            try:
                yield connection

            except Exception as e:
                await connection.rollback()

                raise DatabaseError(*e.args) from e

    async def test_connection(self):
        try:
            async with self.connection() as connection:
                await connection.rollback()

        except Exception as e:
            raise DatabaseError(
                "Failed to connect", self.config.to_string_url(credentials=False)
            ) from e

    async def shutdown(self):
        await self.engine.dispose()

    @asynccontextmanager
    async def session(self) -> AsyncSessionContext:
        session = self.sessionmaker()

        try:
            yield session

        except (HTTPException, ValidationError) as e:
            await session.rollback()
            raise e from None

        except Exception as e:
            await session.rollback()
            raise e

        finally:
            await session.close()

    async def create_user(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        connection: Optional[AsyncConnection] = None,
    ):
        exit_stack = AsyncExitStack()
        conn = connection or await exit_stack.enter_async_context(self.connection())

        async with exit_stack:
            await conn.execute(
                sa.text(
                    f"create role {quoted_name(username or self.config.username, False)} login password :password"
                )
                .bindparams(password=password or self.config.password)
                .compile(compile_kwargs={"literal_binds": True}),
            )
            await conn.commit()

    async def drop_user(
        self,
        username: Optional[str] = None,
        connection: Optional[AsyncConnection] = None,
    ):
        exit_stack = AsyncExitStack()
        conn = connection or await exit_stack.enter_async_context(self.connection())

        async with exit_stack:
            await conn.execute(
                sa.text(
                    f"drop role {quoted_name(username or self.config.username, False)}"
                )
            )
            await conn.commit()

    async def create_database(
        self,
        database: Optional[str] = None,
        username: Optional[str] = None,
        connection: Optional[AsyncConnection] = None,
    ):
        exit_stack = AsyncExitStack()
        conn = connection or await exit_stack.enter_async_context(self.connection())

        async with exit_stack:
            await conn.execution_options(isolation_level="AUTOCOMMIT")
            await conn.execute(
                sa.text(
                    f"create database {quoted_name(database or self.config.database, False)} owner {quoted_name(username or self.config.username, False)}"
                )
            )
            await conn.commit()

    async def drop_database(
        self,
        database: Optional[str] = None,
        connection: Optional[AsyncConnection] = None,
    ):
        exit_stack = AsyncExitStack()
        conn = connection or await exit_stack.enter_async_context(self.connection())

        async with exit_stack:
            await conn.execution_options(isolation_level="AUTOCOMMIT")
            await conn.execute(
                sa.text(
                    f"drop database {quoted_name(database or self.config.database, False)}"
                )
            )
            await conn.commit()

    async def usage(
        self,
        database: Optional[str] = None,
        connection: Optional[AsyncConnection] = None,
    ) -> int:
        exit_stack = AsyncExitStack()
        conn = connection or await exit_stack.enter_async_context(self.connection())

        async with exit_stack:
            query = await conn.execute(
                sa.text("select pg_database_size(:database)")
                .bindparams(database=database or self.config.database)
                .compile(compile_kwargs={"literal_binds": True}),
            )
            await conn.rollback()

            return query.scalar()

        return 0

    async def connection_count(
        self,
        database: Optional[str] = None,
        connection: Optional[AsyncConnection] = None,
    ) -> int:
        exit_stack = AsyncExitStack()
        conn = connection or await exit_stack.enter_async_context(self.connection())

        async with exit_stack:
            query = await conn.execute(
                sa.text("select sum(numbackends) from pg_stat_database")
            )
            await conn.rollback()

            return query.scalar()

        return 0


class PostgresDatabase(SyncDatabase):
    def __init__(self, config: PostgresConfig, **connection_kwargs):
        _connection_kwargs = {
            "pool_size": 100,
            # "poolclass": NullPool,
            "connect_args": {"options": "-c timezone=utc"},
        }
        _connection_kwargs.update(connection_kwargs)

        self.engine: Engine = create_engine(
            config.to_string_url(), **_connection_kwargs
        )

        self.sessionmaker: SessionMaker = sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )

        self.config: PostgresConfig = config

    @contextmanager
    def connection(self) -> ConnectionContext:
        with self.engine.connect() as connection:
            try:
                yield connection

            except Exception as e:
                connection.rollback()

                raise DatabaseError(*e.args) from e

    def test_connection(self):
        try:
            with self.connection() as connection:
                connection.rollback()

        except Exception as e:
            raise DatabaseError(
                "Failed to connect", self.config.to_string_url(credentials=False)
            ) from e

    def shutdown(self):
        self.engine.dispose()

    @contextmanager
    def session(self) -> SessionContext:
        session = self.sessionmaker()

        try:
            yield session

        except (HTTPException, ValidationError) as e:
            session.rollback()
            raise e from None

        except Exception as e:
            session.rollback()
            raise e

        finally:
            session.close()

    def create_user(self):
        with self.connection() as connection:
            connection.execution_options(isolation_level="AUTOCOMMIT")
            connection.execute(
                sa.text("create role :username login").bindparams(
                    username=self.config.username
                )
            )
            connection.commit()

    def drop_user(self):
        with self.connection() as connection:
            connection.execution_options(isolation_level="AUTOCOMMIT")
            connection.execute(
                sa.text("drop role :username").bindparams(username=self.config.username)
            )
            connection.commit()

    def create_database(self):
        with self.connection() as connection:
            connection.execution_options(isolation_level="AUTOCOMMIT")
            connection.execute(
                sa.text("create database :database owner :username").bindparams(
                    database=self.config.database, username=self.config.username
                )
            )
            connection.commit()

    def drop_database(self):
        with self.connection() as connection:
            connection.execution_options(isolation_level="AUTOCOMMIT")
            connection.execute(
                sa.text("drop database :database").bindparams(
                    database=self.config.database
                )
            )
            connection.commit()

    def usage(self) -> int:
        with self.connection() as connection:
            return (
                connection.execute(
                    sa.text("select pg_database_size(:database)").bindparams(
                        database=self.config.database
                    )
                )
            ).scalar()

    def connection_count(
        self,
    ) -> int:
        with self.connection() as connection:
            return (
                connection.execute(
                    sa.text("select sum(numbackends) from pg_stat_database")
                )
            ).scalar()
