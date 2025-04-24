from uuid import UUID
from sqlalchemy import Connection, Integer, String, create_engine, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
import pytest
import asyncio
from typing import Optional
import os

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "firebird://SYSDBA:1@localhost:3050//db/test.fdb"
)


class Base(DeclarativeBase):
    pass


class SketchySession(Session):
    async def connection(self, bind_arguments=None, execution_options=None):
        return asyncio.to_thread(super().connection, bind_arguments, execution_options)


class User(Base):
    __tablename__ = "some_table"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(30))
    age: Mapped[int] = mapped_column(Integer())


@pytest.mark.asyncio
async def test_async_session():
    engine = create_engine(
        DATABASE_URL,
        echo=True,
    )
    s = SketchySession(engine)
    print(f"{s=}")
    query = select(User.name)
    print(f"{query=}")
    results = s.scalars(select(User.name))
    print(results.fetchall())


@pytest.mark.asyncio
async def test_create_engine():
    def test():
        engine = create_engine(
            DATABASE_URL,
            echo=True,
        )
        connection = engine.connect()
        connection.rollback()
        connection.execute(text("select * from users;"))

    await asyncio.to_thread(test)


@pytest.mark.asyncio
async def test_create_table():
    engine = create_engine(
        DATABASE_URL,
        echo=True,
    )
    Base.metadata.create_all(engine)


@pytest.mark.asyncio
async def test_get_table():
    engine = create_engine(
        DATABASE_URL,
        echo=True,
    )
    with Session(engine) as s:
        print(f"{s=}")
        query = select(User.name)
        print(f"{query=}")
        results = s.scalars(select(User.name))
        print(results.fetchall())
