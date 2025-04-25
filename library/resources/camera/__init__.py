from typing import Optional, Self, TypeAlias, cast
from uuid import UUID

from pydantic import ConfigDict
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


class CameraBase(SQLModel):
    name: str = "Unknown"
    is_disabled: bool = False

    stream_url: Optional[str] = None

    station_uuid: Optional[UUID] = Field(
        default=None,
        foreign_key="station.uuid",
        ondelete="SET NULL",
        nullable=True,
        sa_type=GUID,
    )


class CameraPrivate(CameraBase): ...


class CameraPublic(CameraBase, AuditModel):
    model_config = cast(SQLModelConfig, ConfigDict(from_attributes=True))

    uuid: UUID


class CameraCreate(CameraBase): ...


class CameraUpdate(SQLModel):
    name: Optional[str] = None
    is_disabled: Optional[bool] = None

    stream_url: Optional[str] = None

    station_uuid: Optional[UUID] = None


class Camera(UUIDModel, AuditModel, CameraBase, table=True):
    __tablename__ = "camera"  # type: ignore

    station: "Station" = Relationship(back_populates="cameras")

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
    async def new(cls, session: AsyncSession, station_data: CameraCreate) -> Self:
        station = cls(**CameraBase.model_validate(station_data).model_dump())

        return await station.create(session)

    async def update(self, session: AsyncSession, station_data: CameraUpdate) -> Self:
        for field, value in station_data.model_dump(exclude_unset=True).items():
            setattr(self, field, value)

        return await self.refresh(session)

    async def public(self, session: AsyncSession) -> CameraPublic:
        session.add(self)

        public_info = CameraPublic.model_validate(self)

        return public_info

    def is_attached(self) -> bool:
        return self.station_uuid is not None

    async def remove_station(self, session: AsyncSession) -> Self:
        self.station_uuid = None

        return await self.refresh(session)

    async def refresh_station(
        self, session: AsyncSession, station: "Optional[UUID | Station]"
    ) -> Self:
        if station is None:
            return await self.remove_station(session)

        session.add(self)

        if isinstance(station, UUID):
            self.station_uuid = station
        elif isinstance(station, Station):
            self.station_uuid = station.uuid

        return await self.refresh(session)


class CameraFilter(AuditFilter, PaginationFilter):
    camera_uuids: Optional[list[UUID]] = None
    station_uuids: Optional[list[UUID]] = None

    is_disabled: Optional[bool] = None
    is_attached: Optional[bool] = Field(
        default=None, description="Прикреплён ли к станции?"
    )

    async def process(self, session: AsyncSession) -> FilterResult[Camera]:
        query = select(Camera).select_from(
            select(Camera).join(
                Station,
                Camera.station_uuid == Station.uuid,  # type: ignore
            )
        )

        if self.camera_uuids:
            query = query.where(Camera.uuid.in_(self.camera_uuids))  # type: ignore

        if self.station_uuids:
            query = query.where(Station.uuid.in_(self.station_uuids))  # type: ignore

        if isinstance(self.is_disabled, bool):
            query = query.where(Camera.is_disabled.is_(self.is_disabled))  # type: ignore

        if isinstance(self.is_attached, bool):
            query = query.where(Camera.station_uuid.isnot(None))

        query = self.audit_filter(query, Camera)
        total_count = await session.scalar(select(func.count()).select_from(query))

        query = self.audit_order_filter(query, Camera)
        query = self.pagination_filter(query)

        return FilterResult[Camera](
            content=(await session.scalars(query)).all(),
            total=total_count,
            count=self.count if self.count else total_count,
        )


from library.resources.station import Station  # noqa: E402
