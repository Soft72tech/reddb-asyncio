from datetime import datetime, timezone
from typing import Optional, Self
from uuid import UUID

from sqlmodel import SQLModel

from library.core.database.types import AsyncSession
from library.core.models import FilterResult, PaginationFilter
from library.resources.detector import (
    Detector,
    DetectorFilter,
    DetectorPublic,
)
from library.resources.detector.state import (
    DetectorStateFilter,
)
from library.resources.screening import ScreeningFilter


class DetectorStatsBase(SQLModel):
    is_reachable: bool = False
    is_collecting: bool = False

    today_screenings: int = 0
    total_screenings: int = 0
    synchronized_screenings: int = 0

    total_reachable_time: Optional[float] = None
    expected_reachable_time: Optional[float] = None
    reachable_time_percent: Optional[float] = None

    total_collecting_time: Optional[float] = None
    expected_collecting_time: Optional[float] = None
    collecting_time_percent: Optional[float] = None


class DetectorStats(DetectorStatsBase):
    detector: DetectorPublic

    is_reachable: bool = False
    is_collecting: bool = False

    today_screenings: int = 0
    total_screenings: int = 0
    synchronized_screenings: int = 0

    total_reachable_time: Optional[float] = None
    expected_reachable_time: Optional[float] = None
    reachable_time_percent: Optional[float] = None

    total_collecting_time: Optional[float] = None
    expected_collecting_time: Optional[float] = None
    collecting_time_percent: Optional[float] = None

    @classmethod
    async def new(cls, session: AsyncSession, detector: Detector) -> Self:
        screenings_total_result = await ScreeningFilter(
            start_level_or_rad=1, detector_uuids=[detector.uuid]
        ).process(session)
        screenings_synchronized_result = await ScreeningFilter(
            start_level_or_rad=1, detector_uuids=[detector.uuid], is_synchronized=True
        ).process(session)
        screenings_today_result = await ScreeningFilter(
            detector_uuids=[detector.uuid],
            start_level_or_rad=1,
            start_datetime=datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            ),
        ).process(session)
        detector_state_result = await DetectorStateFilter(count=1).process(session)

        # detector_state_history_result = await DetectorStateHistoryFilter().process(
        #     session
        # )

        # TODO: reachable and collecting time (from detector state history)

        return cls(
            detector=await detector.public(session),
            is_reachable=detector_state_result.content[0].is_reachable
            if detector_state_result.total > 0
            else False,
            is_collecting=detector_state_result.content[0].is_collecting
            if detector_state_result.total > 0
            else False,
            today_screenings=screenings_total_result.total,
            total_screenings=screenings_today_result.total,
            synchronized_screenings=screenings_synchronized_result.total,
        )


class DetectorStatsFilter(PaginationFilter):
    detector_uuids: Optional[list[UUID]] = None
    station_uuids: Optional[list[UUID]] = None

    async def process(self, session: AsyncSession) -> FilterResult[DetectorStats]:
        filter_result = await DetectorFilter(
            station_uuids=self.station_uuids,
            detector_uuids=self.detector_uuids,
            page=self.page,
            count=self.count,
        ).process(session)

        return FilterResult[DetectorStats](
            content=[
                await DetectorStats.new(session, detector)
                for detector in filter_result.content
            ],
            total=filter_result.total,
            count=self.count if self.count else filter_result.total,
        )


class DetectorStatsSummary(SQLModel):
    total: int = 0
    disabled: int = 0
    attached: int = 0

    detector_stats: list[DetectorStats] = []

    @classmethod
    async def new(
        cls, session: AsyncSession, filter: DetectorStatsFilter = DetectorStatsFilter()
    ) -> Self:
        total_result = await DetectorFilter().process(session)
        disabled_result = await DetectorFilter(is_disabled=True).process(session)
        attached_result = await DetectorFilter(is_attached=True).process(session)

        detector_stats_result = await filter.process(session)

        return cls(
            total=total_result.total,
            disabled=disabled_result.total,
            attached=attached_result.total,
            detector_stats=detector_stats_result.content,
        )
