import enum
from enum import auto
from uuid import UUID

from sqlmodel import Column, Enum, Field

from library.core.database.types import GUID
from library.core.models import UUIDModel


class UserAction(enum.Enum):
    auth = auto()
    create = auto()
    modify = auto()
    delete = auto()


class Audit(UUIDModel, table=True):
    user_uuid: UUID = Field(foreign_key="users.uuid", nullable=False, sa_type=GUID)
    user_action: UserAction = Field(nullable=False, sa_column=Column(Enum(UserAction)))
