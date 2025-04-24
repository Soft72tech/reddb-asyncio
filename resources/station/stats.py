from datetime import datetime, timezone
from typing import Optional, Self
from uuid import UUID

from sqlmodel import SQLModel

from library.core.database.types import AsyncSession
from library.core.models import FilterResult, PaginationFilter
from library.resources.detector import DetectorFilter
from library.resources.screening import ScreeningFilter
from library.resources.station import Station, StationFilter, StationPublic


class StationStatsBase(SQLModel):
    total_detectors: int = 0

    today_screenings: int = 0
    total_screenings: int = 0
    synchronized_screenings: int = 0


class StationStats(StationStatsBase):
    station: StationPublic

    @classmethod
    async def new(cls, session: AsyncSession, station: Station) -> Self:
        detectors_total_result = await DetectorFilter(
            station_uuids=[station.uuid]
        ).process(session)

        screenings_today_result = await ScreeningFilter(
            station_uuids=[station.uuid],
            start_level_or_rad=1,
            start_datetime=datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            ),
        ).process(session)
        screenings_total_result = await ScreeningFilter(
            start_level_or_rad=1, station_uuids=[station.uuid]
        ).process(session)
        screenings_synchronized_result = await ScreeningFilter(
            start_level_or_rad=1, station_uuids=[station.uuid], is_synchronized=True
        ).process(session)

        return cls(
            station=await station.public(session),
            total_detectors=detectors_total_result.total,
            today_screenings=screenings_total_result.total,
            total_screenings=screenings_today_result.total,
            synchronized_screenings=screenings_synchronized_result.total,
        )


class StationStatsFilter(PaginationFilter):
    station_uuids: Optional[list[UUID]] = None

    async def process(self, session: AsyncSession) -> FilterResult[StationStats]:
        filter_result = await StationFilter(
            station_uuids=self.station_uuids, page=self.page, count=self.count
        ).process(session)

        return FilterResult[StationStats](
            content=[
                await StationStats.new(session, station)
                for station in filter_result.content
            ],
            total=filter_result.total,
            count=self.count if self.count else filter_result.total,
        )


class StationStatsSummary(SQLModel):
    total: int = 0
    disabled: int = 0

    station_stats: list[StationStats] = []

    @classmethod
    async def new(
        cls, session: AsyncSession, filter: StationStatsFilter = StationStatsFilter()
    ) -> Self:
        total_result = await StationFilter().process(session)
        disabled_result = await StationFilter(is_disabled=True).process(session)

        station_stats_result = await filter.process(session)

        return cls(
            total=total_result.total,
            disabled=disabled_result.total,
            station_stats=station_stats_result.content,
        )
