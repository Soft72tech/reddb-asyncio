import enum
from typing import Any, Optional, Self, cast
from uuid import UUID

from pydantic import ConfigDict
from sqlalchemy import func, select
from sqlmodel import JSON, Column, Enum, Field, Relationship, SQLModel
from sqlmodel.main import SQLModelConfig

from library.core.database.types import AsyncSession
from library.core.models import (
    AuditFilter,
    AuditModel,
    FilterResult,
    PaginationFilter,
    UUIDModel,
)


class DetectorType(str, enum.Enum):
    metal_detector = "metal_detector"
    portable_metal_detector = "portable_metal_detector"
    introscope = "introscope"
    gas_analyzer = "gas_analyzer"


class DetectorModelBase(SQLModel):
    name: str
    type: DetectorType = Field(sa_column=Column(Enum(DetectorType)))
    brand: Optional[str] = None

    # ISSUE: deprecated
    width: Optional[int] = None
    height: Optional[int] = None

    photo_link: Optional[str] = None
    output_info: Optional[dict] = Field(default=None, sa_type=JSON)


class DetectorModelPrivate(DetectorModelBase): ...


class DetectorModelPublic(DetectorModelBase, AuditModel):
    model_config = cast(SQLModelConfig, ConfigDict(from_attributes=True))

    uuid: UUID


class DetectorModelCreate(DetectorModelBase): ...


class DetectorModelUpdate(SQLModel):
    name: Optional[str] = None
    type: DetectorType = Field(sa_column=Column(Enum(DetectorType)))
    brand: Optional[str] = None

    # ISSUE: deprecated
    width: Optional[int] = None
    height: Optional[int] = None

    photo_link: Optional[str] = None
    output_info: Optional[dict] = Field(sa_type=JSON)


class DetectorModel(UUIDModel, AuditModel, DetectorModelPrivate, table=True):
    __tablename__ = "detector_model"  # type: ignore

    detectors: list["Detector"] = Relationship(back_populates="model")

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
    async def new(
        cls, session: AsyncSession, station_data: DetectorModelCreate
    ) -> Self:
        station = cls(**DetectorModelBase.model_validate(station_data).model_dump())

        return await station.create(session)

    @classmethod
    async def clone(cls, session: AsyncSession, other: Self | dict[str, Any]) -> Self:
        if isinstance(other, dict):
            base = DetectorModelPrivate(**other)
        else:
            base = DetectorModelPrivate.model_validate(other)

        attributes = base.model_dump()
        attributes.update(**other if isinstance(other, dict) else other.model_dump())

        return await cls(**attributes).create(session)

    async def update(
        self, session: AsyncSession, station_data: DetectorModelUpdate
    ) -> Self:
        for field, value in station_data.model_dump(exclude_unset=True).items():
            setattr(self, field, value)

        return await self.refresh(session)

    async def public(self, session: AsyncSession) -> DetectorModelPublic:
        session.add(self)

        public_info = DetectorModelPublic.model_validate(self)

        return public_info


class DetectorModelFilter(AuditFilter, PaginationFilter):
    type: Optional[DetectorType] = None
    brand: Optional[str] = None

    async def process(self, session: AsyncSession) -> FilterResult[DetectorModel]:
        query = select(DetectorModel)

        if isinstance(self.type, DetectorType):
            query = query.where(DetectorModel.type == self.type)  # type: ignore

        if isinstance(self.brand, str):
            query = query.where(DetectorModel.brand.ilike(f"%{self.brand}%"))  # type: ignore

        query = self.audit_filter(query, DetectorModel)
        total_count = await session.scalar(select(func.count()).select_from(query))

        query = self.audit_order_filter(query, DetectorModel)
        query = self.pagination_filter(query)

        return FilterResult[DetectorModel](
            content=(await session.scalars(query)).all(),
            total=total_count,
            count=self.count if self.count else total_count,
        )


from library.resources.detector import Detector  # noqa: E402
