from datetime import datetime, timezone
from typing import Literal, Optional, Self, TypeAlias, cast
from uuid import UUID

from pydantic import AwareDatetime, ConfigDict
from sqlalchemy import Integer, func, or_, select

from sqlalchemy.sql.expression import cast as sqlcast
from sqlmodel import ARRAY, INT, JSON, Column, Field, Relationship, SQLModel, String
from sqlmodel.main import SQLModelConfig

from library.api.responses import PaginationMetadata
from library.core.database.types import GUID, AsyncSession, DateTimeUTC
from library.core.models import (
    AuditFilter,
    AuditModel,
    FilterResult,
    PaginationFilter,
    UUIDModel,
)


class ScreeningBase(SQLModel):
    model_config = cast(SQLModelConfig, ConfigDict(validate_assignment=True))

    triggered_at: AwareDatetime = Field(sa_type=DateTimeUTC)

    is_corrupted: bool = False
    is_synchronized: bool = False

    level: int = Field(ge=0)
    zone: Optional[list[int]] = Field(default=None, sa_column=Column(ARRAY(INT)))

    rad_level: Optional[int] = Field(default=None, ge=0)

    photo_link: Optional[str] = None
    video_links: Optional[list[str]] = Field(
        default=None, sa_column=Column(ARRAY(String))
    )
    event_data: Optional[dict] = Field(default=None, sa_type=JSON)

    detector_uuid: Optional[UUID] = Field(
        default=None,
        foreign_key="detector.uuid",
        nullable=False,
        ondelete="CASCADE",
        sa_type=GUID,
    )


class ScreeningPrivate(ScreeningBase): ...


class ScreeningPublic(ScreeningBase, AuditModel):
    model_config = cast(SQLModelConfig, ConfigDict(from_attributes=True))

    uuid: UUID

    detector: Optional["DetectorPublic"] = None


class ScreeningCreate(ScreeningBase): ...


class ScreeningUpdate(SQLModel):
    level: Optional[int] = None
    zone: Optional[list[int]] = None

    rad_level: Optional[int] = None

    photo_link: Optional[str] = None
    video_links: Optional[list[str]] = None
    event_data: Optional[dict] = None

    is_synchronized: Optional[bool] = None

    detector_uuid: Optional[UUID] = None


class Screening(UUIDModel, AuditModel, ScreeningPrivate, table=True):
    __tablename__ = "screening"  # type: ignore

    detector: "Detector" = Relationship(
        back_populates="screenings", sa_relationship_kwargs={"lazy": "selectin"}
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
    async def new(cls, session: AsyncSession, screening_data: ScreeningCreate) -> Self:
        screening = cls(**ScreeningBase.model_validate(screening_data).model_dump())

        return await screening.create(session)

    async def update(
        self, session: AsyncSession, screening_data: ScreeningUpdate
    ) -> Self:
        for field, value in screening_data.model_dump(exclude_unset=True).items():
            setattr(self, field, value)

        return await self.refresh(session)

    async def public(self, session: AsyncSession) -> ScreeningPublic:
        session.add(self)
        await session.refresh(self, attribute_names=["detector"])

        public_info = ScreeningPublic.model_validate(
            self, update={"detector": await self.detector.public(session)}
        )

        return public_info


class ScreeningFilter(AuditFilter, PaginationFilter):
    detector_uuids: Optional[list[UUID]] = None
    station_uuids: Optional[list[UUID]] = None

    is_synchronized: Optional[bool] = None

    start_level: Optional[int] = None
    end_level: Optional[int] = None

    start_rad_level: Optional[int] = None
    end_rad_level: Optional[int] = None

    start_level_or_rad: Optional[int] = None

    async def process(self, session: AsyncSession) -> FilterResult[Screening]:
        query = (
            select(Screening)
            .join(Detector, Screening.detector_uuid == Detector.uuid)  # type: ignore
            .join(Station, Detector.station_uuid == Station.uuid)  # type: ignore
        )

        if isinstance(self.detector_uuids, list):
            query = query.where(Screening.detector_uuid.in_(self.detector_uuids))  # type: ignore

        if isinstance(self.station_uuids, list):
            query = query.where(Station.uuid.in_(self.station_uuids))  # type: ignore

        if isinstance(self.is_synchronized, bool):
            query = query.where(Screening.is_synchronized == self.is_synchronized)

        if isinstance(self.start_level, int):
            query = query.where(Screening.level >= self.start_level)

        if isinstance(self.end_level, int):
            query = query.where(Screening.level <= self.end_level)

        if isinstance(self.start_level_or_rad, int):
            query = query.where(
                or_(
                    Screening.level >= self.start_level_or_rad,
                    sqlcast(Screening.rad_level, Integer) >= self.start_level_or_rad,
                )
            )

        query = self.audit_filter(query, Screening)
        total_count = await session.scalar(select(func.count()).select_from(query))

        query = self.audit_order_filter(query, Screening)
        query = self.pagination_filter(query)

        return FilterResult[Screening](
            content=(await session.scalars(query)).all(),
            total=total_count,
            count=self.count if self.count else total_count,
        )


from library.resources.detector import Detector, DetectorPublic  # noqa: E402
from library.resources.station import Station  # noqa: E402
