from typing import Any, Optional, Self, cast
from uuid import UUID

from pydantic import ConfigDict
from sqlalchemy import select
from sqlmodel import SQLModel
from sqlmodel.main import SQLModelConfig

from library.core.database.types import AsyncSession
from library.core.models import (
    AuditModel,
    UUIDModel,
)


class LicenseAgreementBase(SQLModel):
    is_accepted: bool = False


class LicenseAgreementPrivate(LicenseAgreementBase): ...


class LicenseAgreementPublic(LicenseAgreementBase, AuditModel):
    model_config = cast(SQLModelConfig, ConfigDict(from_attributes=True))

    uuid: UUID
    text: Optional[str] = None


class LicenseAgreementCreate(LicenseAgreementBase): ...


class LicenseAgreementUpdate(SQLModel):
    is_accepted: Optional[bool] = None


class LicenseAgreement(UUIDModel, AuditModel, LicenseAgreementBase, table=True):
    __tablename__ = "license_agreement"  # type: ignore[assignment]

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
    async def first(cls, session: AsyncSession) -> Optional[Self]:
        return (await session.scalars(select(cls))).first()

    @classmethod
    async def new(
        cls, session: AsyncSession, license_agreement_data: LicenseAgreementCreate
    ) -> Self:
        license_agreement = cls(
            **LicenseAgreementBase.model_validate(license_agreement_data).model_dump()
        )

        return await license_agreement.create(session)

    @classmethod
    async def clone(cls, session: AsyncSession, other: Self | dict[str, Any]) -> Self:
        if isinstance(other, dict):
            base = LicenseAgreementPrivate(**other)
        else:
            base = LicenseAgreementPrivate.model_validate(other)

        attributes = base.model_dump()
        attributes.update(**other if isinstance(other, dict) else other.model_dump())

        return await cls(**attributes).create(session)

    async def update(
        self, session: AsyncSession, license_agreement_data: LicenseAgreementUpdate
    ) -> Self:
        for field, value in license_agreement_data.model_dump(
            exclude_unset=True
        ).items():
            setattr(self, field, value)

        return await self.refresh(session)

    async def public(self, session: AsyncSession) -> LicenseAgreementPublic:
        session.add(self)

        public_info = LicenseAgreementPublic.model_validate(self)

        return public_info


class LicenseAgreementFilter(SQLModel):
    no_text: Optional[bool] = None
