from uuid import UUID, uuid4
from sqlalchemy import (
    Connection,
    ForeignKey,
    Integer,
    String,
    create_engine,
    insert,
    select,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
import pytest
import asyncio
from typing import Optional
import os
from rich.pretty import pprint
from sqlalchemy.sql.ddl import DropTable

# DATABASE_URL = os.environ.get(
#     "DATABASE_URL", "firebird://SYSDBA:1@localhost:3050//db/test.fdb"
# )
DATABASE_URL = os.environ.get(
    "DATABASE_URL", "firebird://SYSDBA:sysdbapass@192.168.130.173:3050//data/dozor.fdb"
)


class Base(DeclarativeBase):
    pass


class SketchySession(Session):
    async def connection(self, bind_arguments=None, execution_options=None):
        return asyncio.to_thread(super().connection, bind_arguments, execution_options)


class User(Base):
    __tablename__ = "user"
    id: Mapped[UUID] = mapped_column(primary_key=True, insert_default=uuid4())
    name: Mapped[str] = mapped_column(String(30))
    age: Mapped[int] = mapped_column(Integer())


class UserShit(Base):
    __tablename__ = "user_shit"
    id: Mapped[UUID] = mapped_column(primary_key=True, insert_default=uuid4())
    shit_name: Mapped[str] = mapped_column(String)
    user: Mapped[UUID] = mapped_column(ForeignKey("user.id"))


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
async def test_create_table():
    engine = create_engine(
        DATABASE_URL,
        echo=True,
    )
    Base.metadata.create_all(engine)


@pytest.mark.asyncio
async def test_get_users():
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
        s.flush()


@pytest.mark.asyncio
async def test_get_table():
    engine = create_engine(
        DATABASE_URL,
        echo=True,
    )
    with Session(engine) as s:
        user = User()
        user.name = "billy the stupido"
        user.age = 12
        s.add(user)
        s.commit()

        shit = UserShit()
        shit.user = user.id
        shit.shit_name = "some shit"
        s.add(shit)
        s.commit()
        s.flush()


@pytest.mark.asyncio
async def test_create_two_connections():
    engine = create_engine(
        DATABASE_URL,
        echo=True,
    )
    s = None
    s2 = None
    try:
        s = Session(engine)
        user = User()
        user.name = "billy the stupido"
        user.age = 12
        s.add(user)
        s.commit()
        s.flush()

        s2 = Session(engine)
        user = s2.scalar(select(User).where(User.id == user.id))
        if user is None:
            raise ValueError("Where is my user????")
        pprint(user)
        shit = UserShit()
        shit.user = user.id
        shit.shit_name = "some shit"
        s2.add(shit)
        s2.commit()
        s2.flush()
    finally:
        if s:
            s.close()
        if s2:
            s2.close()


@pytest.mark.asyncio
async def test_create_real_meta():
    pass


