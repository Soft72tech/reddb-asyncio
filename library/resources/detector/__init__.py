# TODO: rename `model` to `detector_model`
# TODO: move connection options to another model

from datetime import datetime
from typing import Any, Literal, Optional, Self, TypeAlias, cast
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
from library.core.security.password import hash_password, validate_password


class DetectorBase(SQLModel):
    model_config = cast(SQLModelConfig, ConfigDict(validate_assignment=True))

    name: str
    is_disabled: bool = False
    is_synchronized: bool = False

    model_uuid: Optional[UUID] = Field(
        default=None,
        foreign_key="detector_model.uuid",
        nullable=False,
        sa_type=GUID,
    )

    station_uuid: Optional[UUID] = Field(
        default=None,
        foreign_key="station.uuid",
        ondelete="SET NULL",
        nullable=True,
        sa_type=GUID,
    )

    # Connection options (should not be in this model)
    ip: Optional[str] = None
    port: Optional[int] = None
    samba_username: Optional[str] = None
    samba_path: Optional[str] = None


class DetectorPrivate(DetectorBase):
    samba_hashed_password: Optional[str] = None


class DetectorPublic(DetectorBase, AuditModel):
    model_config = cast(SQLModelConfig, ConfigDict(from_attributes=True))

    uuid: UUID

    model: Optional["DetectorModelPublic"] = None
    station: Optional["StationPublic"] = None


class DetectorCreate(DetectorBase):
    samba_password: Optional[str] = None


class DetectorUpdate(SQLModel):
    model_uuid: Optional[UUID] = None
    station_uuid: Optional[UUID] = None

    name: Optional[str] = None
    is_disabled: Optional[bool] = None

    ip: Optional[str] = None
    port: Optional[int] = None
    samba_username: Optional[str] = None
    samba_path: Optional[str] = None
    samba_password: Optional[str] = None


class Detector(UUIDModel, AuditModel, DetectorPrivate, table=True):
    __tablename__ = "detector"  # type: ignore

    model: "DetectorModel" = Relationship(
        back_populates="detectors", sa_relationship_kwargs={"lazy": "selectin"}
    )
    station: "Station" = Relationship(
        back_populates="detectors", sa_relationship_kwargs={"lazy": "selectin"}
    )

    screenings: list["Screening"] = Relationship(
        back_populates="detector", cascade_delete=True
    )
    detector_states: list["DetectorState"] = Relationship(
        back_populates="detector", cascade_delete=True
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
    async def new(cls, session: AsyncSession, station_data: DetectorCreate) -> Self:
        station = cls(**DetectorBase.model_validate(station_data).model_dump())

        return await station.create(session)

    @classmethod
    async def clone(cls, session: AsyncSession, other: Self | dict[str, Any]) -> Self:
        if isinstance(other, dict):
            base = DetectorPrivate(**other)
        else:
            base = DetectorPrivate.model_validate(other)

        attributes = base.model_dump()
        attributes.update(**other if isinstance(other, dict) else other.model_dump())

        return await cls(**attributes).create(session)

    async def update(self, session: AsyncSession, station_data: DetectorUpdate) -> Self:
        for field, value in station_data.model_dump(exclude_unset=True).items():
            if field == "samba_password":
                await self.refresh_samba_password(session, value)

            elif field == "model_uuid":
                await self.refresh_model(session, value)

            elif field == "station_uuid":
                await self.refresh_station(session, value)

            else:
                setattr(self, field, value)

        return await self.refresh(session)

    async def public(self, session: AsyncSession) -> DetectorPublic:
        session.add(self)
        await session.refresh(self, attribute_names=["model"])

        public_info = DetectorPublic.model_validate(
            self, update={"model": await self.model.public(session)}
        )

        if self.is_attached():
            await session.refresh(self, attribute_names=["station"])
            public_info.station = await self.station.public(session)

        return public_info

    def is_attached(self) -> bool:
        return self.station_uuid is not None

    def validate_samba_password(self, samba_password: str) -> bool:
        return validate_password(samba_password, self.hashed_password)

    async def refresh_samba_password(
        self, session: AsyncSession, password: str
    ) -> Self:
        self.hashed_password = hash_password(password)

        return await self.refresh(session)

    async def remove_model(self, session: AsyncSession) -> Self:
        self.model_uuid = None

        return await self.refresh(session)

    async def refresh_model(
        self, session: AsyncSession, model: "Optional[UUID | DetectorModel]"
    ) -> Self:
        if model is None:
            return await self.remove_model(session)

        session.add(self)

        if isinstance(model, UUID):
            self.model_uuid = model
        elif isinstance(model, DetectorModel):
            self.model_uuid = model.uuid

        return await self.refresh(session)

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


class DetectorFilter(AuditFilter, PaginationFilter):
    detector_uuids: Optional[list[UUID]] = None
    station_uuids: Optional[list[UUID]] = None

    is_disabled: Optional[bool] = None
    is_attached: Optional[bool] = Field(
        default=None, description="Прикреплён ли к станции?"
    )

    async def process(self, session: AsyncSession) -> FilterResult[Detector]:
        query = select(Detector).join(
            Station,
            Detector.station_uuid == Station.uuid,  # type: ignore
        )

        if self.detector_uuids:
            query = query.where(Detector.uuid.in_(self.detector_uuids))  # type: ignore

        if self.station_uuids:
            query = query.where(Station.uuid.in_(self.station_uuids))  # type: ignore

        if isinstance(self.is_disabled, bool):
            query = query.where(Detector.is_disabled.is_(self.is_disabled))  # type: ignore

        if isinstance(self.is_attached, bool):
            query = query.where(Detector.station_uuid.isnot(None))

        query = self.audit_filter(query, Detector)
        total_count = await session.scalar(select(func.count()).select_from(query))

        query = self.audit_order_filter(query, Detector)
        query = self.pagination_filter(query)

        return FilterResult[Detector](
            content=(await session.scalars(query)).all(),
            total=total_count,
            count=self.count if self.count else total_count,
        )


from library.resources.detector.model import (  # noqa: E402
    DetectorModel,
    DetectorModelPublic,
)
from library.resources.detector.state import DetectorState  # noqa: E402
from library.resources.screening import Screening  # noqa: E402
from library.resources.station import Station, StationPublic  # noqa: E402
