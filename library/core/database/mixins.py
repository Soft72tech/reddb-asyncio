from datetime import datetime, timezone
from typing import Any, Optional, Self
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import (
    Mapped,
    declarative_mixin,
    mapped_column,
    validates,
)

from library.core.database.types import (
    GUID,
    AsyncSession,
    AsyncSessionContext,
    DateTimeUTC,
)


@declarative_mixin
class Clonable:
    def clone(self) -> Optional[Self]:
        """Clone model.
        Included: columns and values, foreign keys
        Ignored: primary keys, relationships
        """
        # if not inspect(self).persistent:
        #    return

        cloned = self.__class__(
            **{
                key: getattr(self, key)
                for key in self.__table__.columns.keys()
                # ignore primary keys
                if key not in self.__table__.primary_key.columns.keys()
            }
        )

        return cloned


@declarative_mixin
class Serializable:
    def to_dict(self) -> dict[str, Any]:
        return {key: getattr(self, key) for key in self.__table__.columns.keys()}


@declarative_mixin
class UUIDPrimaryKey:
    uuid: Mapped[UUID] = mapped_column(GUID, default=uuid4, primary_key=True)


@declarative_mixin
class Audit:
    created_at: Mapped[datetime] = mapped_column(
        DateTimeUTC(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTimeUTC(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    @validates("created_at", "updated_at")
    def validate_tz_info(self, _: str, value: datetime) -> datetime:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)

        return value


class MissedSession(Exception): ...


@declarative_mixin
class BaseCRUD:
    def __init__(self) -> None:
        self.__session: Optional[AsyncSessionContext] = None

    def with_session(self, session: AsyncSessionContext) -> Self:
        self.__session = session

        return self

    @property
    def _session(self) -> AsyncSession:
        """
        :raises: MissedSession
        """
        if not self.__session:
            raise MissedSession(
                "Session was not specified. Use `.with_session` method."
            )

        return self.__session

    async def create(self, *args, **kwargs) -> Optional[Self]:
        self._session.add(self)

        try:
            await self._session.flush()
        except IntegrityError:
            await self._session.rollback()
            return
        else:
            await self._session.refresh(self)

        return self

    async def get(self, pki: Any, *args, **kwargs) -> Optional[Self]:
        return await self._session.get(self.__class__, pki)

    async def update(self, *args, **kwargs) -> Self:
        self._session.add(self)

        try:
            await self._session.flush()
        except IntegrityError:
            await self._session.rollback()
            return
        else:
            await self._session.refresh(self)

        return self

    async def delete(self, *args, **kwargs) -> Self:
        self._session.add(self)

        try:
            await self._session.delete(self)
            await self._session.flush()
        except IntegrityError:
            await self._session.rollback()
            return
        else:
            await self._session.refresh(self)

        return self
