import re
from enum import Enum, auto
from typing import Optional, Self, TypeAlias, cast
from uuid import UUID

from pydantic import ConfigDict
from sqlalchemy import func, select
from sqlmodel import Field, Relationship, SQLModel, inspect
from sqlmodel.main import SQLModelConfig

from library.core.converters import make_model_optional
from library.core.database.types import GUID, AsyncSession
from library.core.models import (
    AuditFilter,
    AuditModel,
    FilterResult,
    IdModel,
    PaginationFilter,
    UUIDModel,
)
from library.core.security.password import hash_password, validate_password
from library.utils import setnotnull

_valid_username = re.compile(r"^[\da-zA-Z][-.\w]*$")
_invalid_username = re.compile(r"[-._]{2,}|[-._]$")

UserID: TypeAlias = UUID


class UserBase(SQLModel):
    username: str = Field(unique=True)

    name: str
    surname: str
    middle_name: str

    user_role_uuid: Optional[UUID] = Field(
        default=None,
        foreign_key="user_roles.uuid",
        nullable=True,
        sa_type=GUID,
    )


class UserPrivate(UserBase):
    hashed_password: str = Field(min_length=8)


class UserPublic(UserBase, AuditModel):
    model_config = cast(SQLModelConfig, ConfigDict(from_attributes=True))

    uuid: UUID

    user_role: Optional["UserRolePublic"] = None


class UserCreate(UserBase):
    password: str


class UserUpdate(SQLModel):
    username: Optional[str] = None

    name: Optional[str] = None
    surname: Optional[str] = None
    middle_name: Optional[str] = None

    user_role_uuid: Optional[UUID] = None


class UserError(Exception): ...


class User(UUIDModel, AuditModel, UserPrivate, table=True):
    __tablename__ = "users"  # type: ignore

    user_role: "UserRole" = Relationship(
        back_populates="users", sa_relationship_kwargs={"lazy": "joined"}
    )

    async def create(self, session: AsyncSession) -> Self:
        session.add(self)
        await session.flush()

        return self

    async def remove(self, session: AsyncSession) -> Self:
        await session.delete(self)
        await session.flush()

        return self

    async def refresh(self, session: AsyncSession) -> Self:
        self.refresh_updated_at()

        session.add(self)
        await session.flush()

        return self

    @classmethod
    async def with_uuid(cls, session: AsyncSession, uuid: UUID) -> Optional[Self]:
        return await session.scalar(select(cls).where(cls.uuid == uuid))

    @classmethod
    async def new(cls, session: AsyncSession, user_data: UserCreate) -> Self:
        if user_data.user_role_uuid is not None:
            if not await UserRole.with_uuid(session, user_data.user_role_uuid):
                raise UserRoleError(
                    "Invalid user role", f"uuid = {user_data.user_role_uuid}"
                )

        user = User(
            hashed_password=hash_password(user_data.password),
            **UserBase.model_validate(user_data).model_dump(),
        )

        return await user.create(session)  # type:ignore

    async def update(self, session: AsyncSession, user_data: UserUpdate) -> Self:
        for field, value in user_data.model_dump(exclude_unset=True).items():
            if User.model_fields[field].is_required and value is None:
                raise UserError(f"Поле `{field}` не может быть задано нулевым")

            if field == "password":
                await self.refresh_password(session, value)

            elif field == "user_role_uuid":
                await self.refresh_user_role(session, value)

            else:
                setattr(self, field, value)

        return await self.refresh(session)

    async def public(self, session: AsyncSession) -> UserPublic:
        if inspect(self).deleted:
            raise UserError("Пользователь удалён")

        session.add(self)
        await session.refresh(self, attribute_names=["user_role"])

        if self.user_role is not None:
            user_role = await self.user_role.public(session)
            session.expunge(self.user_role)
        else:
            user_role = None

        public_info = UserPublic.model_validate(self)
        public_info.user_role = user_role

        return public_info

    def validate_password(self, password: str) -> bool:
        return validate_password(password, self.hashed_password)

    async def refresh_password(self, session: AsyncSession, password: str) -> Self:
        self.hashed_password = hash_password(password)

        return await self.refresh(session)

    async def remove_user_role(self, session: AsyncSession) -> Self:
        self.user_role_uuid = None

        return await self.refresh(session)

    async def refresh_user_role(
        self, session: AsyncSession, user_role: "Optional[UUID | UserRole]"
    ) -> Self:
        if user_role is None:
            return await self.remove_user_role(session)

        session.add(self)

        if isinstance(user_role, UUID):
            self.user_role_uuid = user_role
        elif isinstance(user_role, UserRole):
            self.user_role_uuid = user_role.uuid

        return await self.refresh(session)


class UserFilter(AuditFilter, PaginationFilter):
    user_uuids: Optional[list[UUID]] = None

    username: Optional[str] = None

    async def process(self, session: AsyncSession) -> FilterResult[User]:
        query = select(User)

        if self.user_uuids:
            query = query.where(User.uuid.in_(self.user_uuids))  # type: ignore

        if isinstance(self.username, str):
            query = query.where(User.name.ilike(f"%{self.username}%"))

        query = self.audit_filter(query, User)
        total_count = await session.scalar(select(func.count()).select_from(query))

        query = self.audit_order_filter(query, User)
        query = self.pagination_filter(query)

        return FilterResult[User](
            content=(await session.scalars(query)).all(),
            total=total_count,
            count=self.count if self.count else total_count,
        )


from library.resources.user.roles import (  # noqa: E402
    UserRole,
    UserRoleError,
    UserRolePublic,
)
