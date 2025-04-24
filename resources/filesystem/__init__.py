from datetime import datetime
from typing import Optional, Self, TypeAlias, cast
from uuid import UUID

from pydantic import ConfigDict
from sqlalchemy import func, select
from sqlmodel import Field, Relationship, SQLModel
from sqlmodel.main import SQLModelConfig

from library.core.abc.cache import AsyncCache
from library.core.database.types import AsyncSession
from library.core.models import (
    AuditFilter,
    AuditModel,
    FilterResult,
    PaginationFilter,
    UUIDModel,
)
from library.settings import ProjectSettings


class FilesystemSettingsBase(SQLModel):
    purge_enabled: bool = True
    purge_cron: str = "* * * * *"
    purge_data_lifetime: int = 30


class FilesystemSettingsPrivate(FilesystemSettingsBase): ...


class FilesystemSettingsPublic(FilesystemSettingsBase, AuditModel):
    model_config = cast(SQLModelConfig, ConfigDict(from_attributes=True))


class FilesystemSettingsCreate(FilesystemSettingsBase): ...


class FilesystemSettingsUpdate(SQLModel):
    purge_enabled: Optional[bool] = None
    purge_cron: Optional[str] = None
    purge_data_lifetime: Optional[int] = None


class FilesystemSettings(UUIDModel, AuditModel, FilesystemSettingsBase, table=True):
    __tablename__ = "filesystem_settings"  # type: ignore

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
    async def load(cls, session: AsyncSession) -> Optional[Self]:
        return await session.scalar(select(cls))

    @classmethod
    async def new(
        cls, session: AsyncSession, filesystem_settings_data: FilesystemSettingsCreate
    ) -> Self:
        filesystem_settings = cls(
            **FilesystemSettingsBase.model_validate(
                filesystem_settings_data
            ).model_dump()
        )

        return await filesystem_settings.create(session)

    async def update(
        self, session: AsyncSession, filesystem_settings_data: FilesystemSettingsUpdate
    ) -> Self:
        for field, value in filesystem_settings_data.model_dump(
            exclude_unset=True
        ).items():
            setattr(self, field, value)

        return await self.refresh(session)

    async def public(self, session: AsyncSession) -> FilesystemSettingsPublic:
        session.add(self)

        public_info = FilesystemSettingsPublic.model_validate(self)

        return public_info


class FilesystemPurge(SQLModel):
    filesystem_settings: FilesystemSettingsPublic

    last_scheduled_purge: Optional[datetime] = None
    last_manual_purge: Optional[datetime] = None

    @classmethod
    async def new(
        cls,
        session: AsyncSession,
        cache: AsyncCache,
        filesystem_settings: FilesystemSettings,
    ) -> Self:
        last_scheduled_purge = None
        last_manual_purge = None

        async with cache.client() as cache:
            if value := await cache.get("last_scheduled_purge"):
                last_scheduled_purge = datetime.fromisoformat(value)

            if value := await cache.get("last_manual_purge"):
                last_manual_purge = datetime.fromisoformat(value)

        return cls(
            filesystem_settings=await filesystem_settings.public(session),
            last_scheduled_purge=last_scheduled_purge,
            last_manual_purge=last_manual_purge,
        )


class FilesystemPurgeStats(FilesystemPurge):
    filesystem_settings: FilesystemSettingsPublic
