from datetime import datetime, timezone
from typing import Self

from sqlmodel import SQLModel

from library.core.database.types import AsyncSession
from library.resources.screening import ScreeningFilter


class ScreeningStatsSummary(SQLModel):
    total: int = 0
    synchronized: int = 0
    today: int = 0

    @classmethod
    async def new(cls, session: AsyncSession) -> Self:
        total_result = await ScreeningFilter(start_level=1).process(session)
        synchronized_result = await ScreeningFilter(
            start_level_or_rad=1, is_synchronized=True
        ).process(session)
        today_result = await ScreeningFilter(
            start_level_or_rad=1,
            start_datetime=datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            ),
        ).process(session)

        return cls(
            total=total_result.total,
            synchronized=synchronized_result.total,
            today=today_result.total,
        )
