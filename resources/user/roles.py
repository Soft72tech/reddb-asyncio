from typing import Optional, Self, cast
from uuid import UUID

from pydantic import ConfigDict, TypeAdapter, ValidationError
from sqlalchemy import func, select
from sqlmodel import Field, Relationship, SQLModel
from sqlmodel.main import SQLModelConfig

from library.core.database.types import GUID, AsyncSession
from library.core.models import (
    AuditFilter,
    AuditModel,
    FilterResult,
    PaginationFilter,
    UUIDModel,
)
from library.resources.oauth2.scope import OAuth2Scopes


class UserRoleError(Exception): ...


class UserAllowedStation(UUIDModel, table=True):
    __tablename__ = "user_allowed_stations"  # type: ignore

    user_role_uuid: UUID = Field(
        foreign_key="user_roles.uuid",
        nullable=False,
        sa_type=GUID,
        ondelete="CASCADE",
    )
    user_roles: list["UserRole"] = Relationship(back_populates="user_allowed_stations")

    station_uuid: UUID = Field(
        foreign_key="station.uuid",  # TODO: move to 'stations.uuid'
        nullable=False,
        sa_type=GUID,
        ondelete="CASCADE",
    )
    stations: list["Station"] = Relationship(back_populates="user_allowed_stations")

    async def create(self, session: AsyncSession) -> Self:
        session.add(self)
        await session.flush()

        return self

    async def remove(self, session: AsyncSession) -> Self:
        await session.delete(self)
        await session.flush()

        return self

    @classmethod
    def _extract_user_role_uuid(cls, user_role: "UUID | UserRole") -> Optional[UUID]:
        user_role_uuid = None

        if isinstance(user_role, UserRole):
            user_role_uuid = user_role.uuid
        elif isinstance(user_role, UUID):
            user_role_uuid = user_role

        return user_role_uuid

    @classmethod
    async def remove_associated_role(
        cls, session: AsyncSession, user_role: "UUID | UserRole"
    ) -> list[Self]:
        if not (user_role_uuid := cls._extract_user_role_uuid(user_role)):
            raise UserRoleError(
                "Cannot remove stations associated with role without identity key."
            )

        return [
            await user_allowed_station.remove(session)
            for user_allowed_station in (
                await session.scalars(
                    select(UserAllowedStation).where(UserRole.uuid == user_role_uuid)
                )
            )
        ]

    @classmethod
    async def add_associated_role(
        cls,
        session: AsyncSession,
        user_role: "UUID | UserRole",
        stations: "list[UUID] | list[Station]",
    ) -> list[Self]:
        try:
            allowed_stations = TypeAdapter(list[Station]).validate_python(stations)

        except ValidationError:
            allowed_stations = (
                await session.scalars(
                    select(Station).where(Station.uuid.in_(stations))  # type: ignore
                )
            ).all()

        if not (user_role_uuid := cls._extract_user_role_uuid(user_role)):
            raise UserRoleError(
                "Cannot add stations associated with role without identity key."
            )

        user_allowed_stations = [
            cls(user_role_uuid=user_role_uuid, station_uuid=allowed_station.uuid)
            for allowed_station in allowed_stations
        ]

        session.add_all(user_allowed_stations)
        await session.flush()

        return user_allowed_stations

    @classmethod
    async def associated_role(
        cls, session: AsyncSession, user_role: "UUID | UserRole"
    ) -> list[Self]:
        if not (user_role_uuid := cls._extract_user_role_uuid(user_role)):
            raise UserRoleError(
                "Cannot get stations associated with role without identity key."
            )

        return (
            await session.scalars(
                select(UserAllowedStation).where(
                    UserAllowedStation.user_role_uuid == user_role_uuid
                )
            )
        ).all()


class UserRoleBase(SQLModel):
    name: str


class UserRolePrivate(UserRoleBase):
    oauth2_grant_uuid: Optional[UUID] = Field(
        default=None,
        foreign_key="oauth2_grants.uuid",
        nullable=True,
        sa_type=GUID,
    )
    is_protected: bool = False
    is_privileged: bool = False


class UserRoleCreate(UserRoleBase):
    scopes: Optional[list[str]] = None
    user_allowed_station_uuids: Optional[list[UUID]] = None


class UserRoleUpdate(SQLModel):
    name: Optional[str] = None
    scopes: Optional[list[str]] = None
    user_allowed_station_uuids: Optional[list[UUID]] = None


class UserRolePublic(UserRoleCreate, AuditModel):
    model_config = cast(SQLModelConfig, ConfigDict(from_attributes=True))

    uuid: UUID
    is_protected: Optional[bool] = None
    is_privileged: Optional[bool] = False


class UserRole(UUIDModel, AuditModel, UserRolePrivate, table=True):
    __tablename__ = "user_roles"  # type:ignore

    users: list["User"] = Relationship(back_populates="user_role")

    oauth2_grant: "OAuth2Grant" = Relationship(
        back_populates="user_role",
    )

    user_allowed_stations: list["UserAllowedStation"] = Relationship(
        back_populates="user_roles",
        link_model=UserAllowedStation,
        sa_relationship_kwargs={
            "secondaryjoin": "UserRole.uuid == UserAllowedStation.user_role_uuid",
            "viewonly": True,
        },
        cascade_delete=True,
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
    async def new(cls, session: AsyncSession, user_role_data: UserRoleCreate) -> Self:
        user_role = UserRole.model_validate(UserRoleBase.model_validate(user_role_data))

        session.add(user_role)
        await session.flush()

        if user_role_data.scopes:
            await user_role.refresh_grant(session, user_role_data.scopes)

        if user_role_data.user_allowed_station_uuids:
            await user_role.refresh_user_allowed_stations(
                session, user_role_data.user_allowed_station_uuids
            )

        return await user_role.create(session)  # type:ignore

    async def update(
        self, session: AsyncSession, user_role_data: UserRoleUpdate
    ) -> Self:
        for field, value in user_role_data.model_dump(exclude_unset=True).items():
            if field == "scopes":
                self.check_readonly()
                await self.refresh_grant(session, value)

            elif field == "user_allowed_station_uuids":
                await self.refresh_user_allowed_stations(session, value)

            else:
                self.check_readonly()
                setattr(self, field, value)

        return await self.refresh(session)

    async def public(self, session: AsyncSession) -> UserRolePublic:
        session.add(self)

        public_info = UserRolePublic.model_validate(self)
        public_info.user_allowed_station_uuids = await self._user_allowed_station_uuids(
            session
        )
        # Frontend doesn't want to know about self:read scope
        scopes = await self._scopes(session)
        public_info.scopes = (
            list(filter(lambda scope: scope != "self:read", scopes)) if scopes else None
        )

        return public_info

    def check_readonly(self):
        if self.is_protected is True:
            raise UserRoleError("Пользовательская роль защищена от редактирования")

    async def remove_user_allowed_stations(self, session: AsyncSession) -> Self:
        if not self.uuid:
            return self

        await UserAllowedStation.remove_associated_role(session, self.uuid)

        await self.refresh(session)
        await session.refresh(self, attribute_names=["user_allowed_stations"])

        return self

    async def refresh_user_allowed_stations(
        self, session: AsyncSession, user_allowed_station_uuids: Optional[list[UUID]]
    ) -> Self:
        # don't check protection flag

        if user_allowed_station_uuids is None:
            return await self.remove_user_allowed_stations(session)

        session.add(self)
        await session.refresh(self, attribute_names=["user_allowed_stations"])

        await UserAllowedStation.remove_associated_role(session, self.uuid)

        station_uuids = (
            await session.scalars(
                select(Station.uuid).where(  # type:ignore
                    Station.uuid.in_(user_allowed_station_uuids)  # type:ignore
                )
            )
        ).all()

        self.user_allowed_stations = await UserAllowedStation.add_associated_role(
            session, self.uuid, station_uuids
        )

        return await self.refresh(session)

    async def allowed_station_uuids(self, session: AsyncSession) -> list[UUID]:
        return (
            await session.scalars(
                select(UserAllowedStation.station_uuid).where(
                    UserAllowedStation.user_role_uuid == self.uuid
                )
            )
        ).all()

    async def remove_grant(self, session: AsyncSession) -> Self:
        self.check_readonly()

        session.add(self)
        await session.refresh(self, attribute_names=["oauth2_grant"])

        if self.oauth2_grant:
            await self.oauth2_grant.remove(session)
            self.oauth2_grant_uuid = None
            await session.refresh(self, attribute_names=["oauth2_grant"])

        return await self.refresh(session)

    async def refresh_grant(
        self, session: AsyncSession, scopes: Optional[list[str]]
    ) -> Self:
        self.check_readonly()

        if scopes is None:
            return await self.remove_grant(session)

        oauth2_scopes = OAuth2Scopes.from_list(scopes).as_str()

        session.add(self)
        await session.refresh(self, attribute_names=["oauth2_grant"])

        if not self.oauth2_grant:
            oauth2_grant = await OAuth2Grant(scopes=oauth2_scopes).create(session)
            self.oauth2_grant_uuid = oauth2_grant.uuid

        else:
            await self.oauth2_grant.refresh_scopes(session, scopes)

        return await self.refresh(session)

    async def _user_allowed_station_uuids(
        self, session: AsyncSession
    ) -> Optional[list[UUID]]:
        if not (
            allowed_stations := await UserAllowedStation.associated_role(
                session, self.uuid
            )
        ):
            return

        return list(
            map(lambda allowed_station: allowed_station.station_uuid, allowed_stations)
        )

    async def _scopes(self, session: AsyncSession) -> Optional[list[str]]:
        await session.refresh(self, attribute_names=["oauth2_grant"])

        if self.oauth2_grant is None:
            return

        return OAuth2Scopes.from_str(self.oauth2_grant.scopes).as_list()


class UserRoleFilter(AuditFilter, PaginationFilter):
    user_role_uuids: Optional[list[UUID]] = None

    name: Optional[str] = None

    async def process(self, session: AsyncSession) -> FilterResult[UserRole]:
        query = select(UserRole)

        if self.user_role_uuids:
            query = query.where(UserRole.uuid.in_(self.user_role_uuids))  # type: ignore

        if isinstance(self.name, str):
            query = query.where(UserRole.name.ilike(f"%{self.name}%"))

        query = self.audit_filter(query, UserRole)
        total_count = await session.scalar(select(func.count()).select_from(query))

        query = self.audit_order_filter(query, UserRole)
        query = self.pagination_filter(query)

        return FilterResult[UserRole](
            content=(await session.scalars(query)).all(),
            total=total_count,
            count=self.count if self.count else total_count,
        )


from library.resources.oauth2.grant import OAuth2Grant  # noqa: E402
from library.resources.station import Station  # noqa: E402
from library.resources.user import User  # noqa: E402
