from datetime import datetime
from typing import Optional, Self, cast
from uuid import UUID

from pydantic import ConfigDict
from sqlalchemy import func, select, union
from sqlalchemy.orm import aliased
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


class DetectorStateBase(SQLModel):
    is_reachable: bool = False
    is_collecting: bool = False
    is_synchronized: bool = False

    detector_uuid: Optional[UUID] = Field(
        default=None,
        foreign_key="detector.uuid",
        nullable=False,
        ondelete="CASCADE",
        sa_type=GUID,
    )


class DetectorStatePrivate(DetectorStateBase): ...


class DetectorStatePublic(DetectorStateBase, AuditModel):
    model_config = cast(SQLModelConfig, ConfigDict(from_attributes=True))

    uuid: UUID


class DetectorStateCreate(DetectorStateBase): ...


class DetectorStateUpdate(SQLModel):
    is_synchronized: Optional[bool] = False


class DetectorState(UUIDModel, AuditModel, DetectorStateBase, table=True):
    __tablename__ = "detector_state"  # type: ignore

    detector: "Detector" = Relationship(back_populates="detector_states")

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
        cls, session: AsyncSession, station_data: DetectorStateCreate
    ) -> Self:
        station = cls(**DetectorStateBase.model_validate(station_data).model_dump())

        return await station.create(session)

    async def update(
        self, session: AsyncSession, station_data: DetectorStateUpdate
    ) -> Self:
        for field, value in station_data.model_dump(exclude_unset=True).items():
            setattr(self, field, value)

        return await self.refresh(session)

    async def public(self, session: AsyncSession) -> DetectorStatePublic:
        session.add(self)
        await session.refresh(self, attribute_names=["detector"])

        public_info = DetectorStatePublic.model_validate(self)

        return public_info


class DetectorStateFilter(AuditFilter, PaginationFilter):
    is_reachable: Optional[bool] = None
    is_collecting: Optional[bool] = None
    is_synchronized: Optional[bool] = None

    async def process(self, session: AsyncSession) -> FilterResult[DetectorState]:
        query = select(DetectorState).join(
            Detector,
            DetectorState.detector_uuid == Detector.uuid,  # type: ignore
        )

        if isinstance(self.is_reachable, bool):
            query = query.where(DetectorState.is_reachable.is_(self.is_reachable))  # type: ignore

        if isinstance(self.is_collecting, bool):
            query = query.where(DetectorState.is_collecting.is_(self.is_collecting))  # type: ignore

        if isinstance(self.is_synchronized, bool):
            query = query.where(DetectorState.is_synchronized.is_(self.is_synchronized))

        query = self.audit_filter(query, DetectorState)
        total_count = await session.scalar(select(func.count()).select_from(query))

        query = self.audit_order_filter(query, DetectorState)
        query = self.pagination_filter(query)

        return FilterResult[DetectorState](
            content=(await session.scalars(query)).all(),
            total=total_count,
            count=self.count if self.count else total_count,
        )


class DetectorStateInterval(DetectorStateBase):
    start_datetime: datetime
    end_datetime: Optional[datetime] = None
    detector: "DetectorPublic"


class DetectorStateHistoryFilter(AuditFilter, PaginationFilter):
    is_reachable: Optional[bool] = None
    is_collecting: Optional[bool] = None

    detector_uuids: Optional[list[UUID]] = Field(default=None, alias="detector_uuids[]")
    station_uuids: Optional[list[UUID]] = Field(default=None, alias="station_uuids[]")

    async def process(
        self, session: AsyncSession
    ) -> FilterResult[DetectorStateInterval]:
        base_join = (
            select(DetectorState)
            .join(Detector, DetectorState.detector_uuid == Detector.uuid)
            .join(Station, Detector.station_uuid == Station.uuid)
        )
        union_query = []

        if self.is_reachable is not None:
            base_join = base_join.where(DetectorState.is_reachable == self.is_reachable)

        if self.is_collecting is not None:
            base_join = base_join.where(
                DetectorState.is_collecting == self.is_collecting
            )

        if self.detector_uuids:
            base_join = base_join.where(Detector.uuid.in_(self.detector_uuids))

        if self.station_uuids:
            base_join = base_join.where(Station.uuid.in_(self.station_uuids))

        # spliting query filters from this point
        query = base_join

        query = self.audit_filter(query, DetectorState)

        if self.start_datetime:
            # left interval
            union_query.append(
                base_join.where(
                    DetectorState.created_at.in_(
                        select(func.max(DetectorState.created_at))
                        .where(DetectorState.created_at < self.start_datetime)
                        .group_by(DetectorState.detector_uuid)
                    )
                )
            )

        if self.end_datetime:
            # right interval
            union_query.append(
                base_join.where(
                    DetectorState.created_at.in_(
                        select(func.min(DetectorState.created_at))
                        .where(DetectorState.created_at > self.end_datetime)
                        .group_by(DetectorState.detector_uuid)
                    )
                )
            )

        union_query.append(query)
        query = union(*union_query).order_by(DetectorState.created_at.asc()).subquery()

        total_count = await session.scalar(select(func.count()).select_from(query))

        detector_states = (
            await session.scalars(select(aliased(DetectorState, query)))
        ).all()
        history = []
        detector_uuids = set()

        for state in detector_states:
            await session.refresh(state, attribute_names=["detector"])
            detector_uuids.add(state.detector.uuid)

        for detector_uuid in detector_uuids:
            _detector_states = list(
                filter(
                    lambda state: state.detector.uuid == detector_uuid,
                    detector_states,
                )
            )
            for n, detector_state in enumerate(_detector_states):
                state = DetectorStateInterval(
                    **detector_state.model_dump(),
                    start_datetime=detector_state.created_at,
                    detector=await detector_state.detector.public(session),
                )

                try:
                    next_detector_state = _detector_states[n + 1]
                except IndexError:
                    # no end state
                    pass
                else:
                    state.end_datetime = next_detector_state.created_at

                history.append(state)

        history.sort(
            key=lambda v: v.start_datetime,
            reverse=self.order_by == "end_datetime",
        )
        count = 0

        if self.count:
            offset = (self.page - 1) * self.count

            if offset + self.count > len(history):
                limit = len(history) - offset
            else:
                limit = self.count

            count = offset + limit

            history = history[offset:count]

        return FilterResult[DetectorStateInterval](
            content=history,
            total=total_count,
            count=count if self.count else total_count,
        )


from library.resources.detector import Detector, DetectorPublic  # noqa: E402
from library.resources.station import Station  # noqa: E402
