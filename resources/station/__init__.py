from typing import Any, Optional, Self, Type, TypeAlias, cast
from uuid import UUID

from pydantic import ConfigDict
from sqlalchemy import func, select
from sqlmodel import Field, Relationship, SQLModel
from sqlmodel.main import SQLModelConfig

from library.core.database.types import AsyncSession
from library.core.models import (
    AuditFilter,
    AuditModel,
    FilterResult,
    PaginationFilter,
    UUIDModel,
)


class StationBase(SQLModel):
    model_config = cast(SQLModelConfig, ConfigDict(validate_assignment=True))

    name: str
    is_disabled: bool = False
    is_synchronized: bool = False


class StationPrivate(StationBase): ...


class StationPublic(StationBase, AuditModel):
    model_config = cast(SQLModelConfig, ConfigDict(from_attributes=True))

    uuid: UUID


class StationCreate(StationBase): ...


class StationUpdate(SQLModel):
    name: Optional[str] = None
    is_disabled: Optional[bool] = None


class Station(UUIDModel, AuditModel, StationBase, table=True):
    __tablename__ = "station"  # type: ignore

    detectors: list["Detector"] = Relationship(back_populates="station")
    cameras: list["Camera"] = Relationship(back_populates="station")

    user_allowed_stations: list["UserAllowedStation"] = Relationship(
        back_populates="stations",
        sa_relationship_kwargs={
            "secondary": "user_allowed_stations",
            "secondaryjoin": "Station.uuid == UserAllowedStation.station_uuid",
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
    async def new(cls, session: AsyncSession, station_data: StationCreate) -> Self:
        station = cls(**StationBase.model_validate(station_data).model_dump())

        return await station.create(session)

    @classmethod
    async def clone(cls, session: AsyncSession, other: Self | dict[str, Any]) -> Self:
        if isinstance(other, dict):
            base = StationPrivate(**other)
        else:
            base = StationPrivate.model_validate(other)

        attributes = base.model_dump()
        attributes.update(**other if isinstance(other, dict) else other.model_dump())

        return await cls(**attributes).create(session)

    async def update(self, session: AsyncSession, station_data: StationUpdate) -> Self:
        for field, value in station_data.model_dump(exclude_unset=True).items():
            setattr(self, field, value)

        return await self.refresh(session)

    async def public(self, session: AsyncSession) -> StationPublic:
        session.add(self)

        public_info = StationPublic.model_validate(self)

        return public_info

    async def attach_detector(
        self, session: AsyncSession, detector: "UUID | Detector"
    ) -> Self: ...

    async def detach_detector(
        self, session: AsyncSession, detector: "UUID | Detector"
    ) -> Self: ...

    async def attach_camera(
        self, session: AsyncSession, camera: "UUID | Camera"
    ) -> Self: ...

    async def detach_camera(
        self, session: AsyncSession, camera: "UUID | Camera"
    ) -> Self: ...


class StationFilter(AuditFilter, PaginationFilter):
    station_uuids: Optional[list[UUID]] = None

    is_disabled: Optional[bool] = None

    async def process(self, session: AsyncSession) -> FilterResult[Station]:
        query = select(Station)

        if self.station_uuids:
            query = query.where(Station.uuid.in_(self.station_uuids))  # type: ignore

        if isinstance(self.is_disabled, bool):
            query = query.where(Station.is_disabled.is_(self.is_disabled))  # type: ignore

        query = self.audit_filter(query, Station)
        total_count = await session.scalar(select(func.count()).select_from(query))

        query = self.audit_order_filter(query, Station)
        query = self.pagination_filter(query)

        return FilterResult[Station](
            content=(await session.scalars(query)).all(),
            total=total_count,
            count=self.count if self.count else total_count,
        )


from library.resources.camera import Camera  # noqa: E402
from library.resources.detector import Detector  # noqa: E402
from library.resources.user.roles import UserAllowedStation  # noqa: E402
