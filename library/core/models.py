from datetime import datetime, timezone
from typing import Annotated, Any, Generic, Literal, Optional, Self, TypeVar
from uuid import UUID, uuid4

from pydantic import AwareDatetime, PlainSerializer
from sqlalchemy.sql import Select
from sqlmodel import Field, SQLModel

from library.core.database.types import GUID, DateTimeUTC


class IdModel(SQLModel):
    id: Optional[int] = Field(
        default=None, primary_key=True, index=True, nullable=False
    )


class UUIDModel(SQLModel):
    uuid: UUID = Field(
        primary_key=True,
        index=True,
        nullable=False,
        default_factory=uuid4,
        sa_type=GUID,
    )


datetime_utc = Annotated[
    datetime,
    PlainSerializer(
        lambda dt: dt.isoformat() + "Z" if not dt.utcoffset() else dt.isoformat()
    ),
    # PlainValidator(lambda raw_dt: raw_dt.strip("Z")),
    # WithJsonSchema({"type": "datetime"}),
]


class TimestampModel(SQLModel):
    created_at: AwareDatetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), sa_type=DateTimeUTC
    )


class AuditModel(TimestampModel):
    updated_at: AwareDatetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), sa_type=DateTimeUTC
    )

    def refresh_updated_at(self) -> Self:
        if default_factory := AuditModel.model_fields["updated_at"].default_factory:
            self.updated_at = default_factory()

        return self


FilterContent = TypeVar("FilterContent")


class FilterResult(SQLModel, Generic[FilterContent]):
    content: list[FilterContent] = []
    total: int
    count: int


class AuditFilter(SQLModel):
    """
    See: `AuditModel`
    """

    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None

    order_by: Literal["start_datetime", "end_datetime"] = "end_datetime"

    def audit_filter(self, query: Select, cls: Any) -> Select:
        if isinstance(self.start_datetime, datetime):
            query = query.where(cls.created_at >= self.start_datetime)

        if isinstance(self.end_datetime, datetime):
            query = query.where(cls.created_at <= self.end_datetime)

        return query

    def audit_order_filter(self, query: Select, cls: Any) -> Select:
        if self.order_by == "end_datetime":
            query = query.order_by(cls.created_at.desc())  # type: ignore

        else:
            query = query.order_by(cls.created_at.asc())  # type: ignore

        return query


class PaginationFilter(SQLModel):
    page: int = Field(default=1, gt=0)
    count: Optional[int] = Field(default=None, gt=0)

    def pagination_filter(self, query: Select) -> Select:
        if self.count:
            query = query.offset((self.page - 1) * self.count).limit(self.count)

        return query
