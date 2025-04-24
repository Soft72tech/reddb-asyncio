import re
from pathlib import Path
from typing import (
    Annotated,
    Any,
    Literal,
    Optional,
    Self,
    TypeAlias,
    cast,
)

from fastapi.encoders import IPv6Address
from pydantic import (
    AnyUrl,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    field_serializer,
    model_validator,
)
from pydantic.networks import IPv4Address, IPvAnyAddress

ErrorCategory = Literal["user", "dev"]
StatusCode: TypeAlias = int


class BaseErrorResponse(BaseModel):
    """
    Base HTTP error response.

    Reference: https://datatracker.ietf.org/doc/html/rfc7807
    """

    status: Optional[StatusCode]
    type: Optional[str] = None
    title: Optional[str] = None
    detail: Optional[str] = None
    # custom fields
    category: Optional[ErrorCategory] = "dev"


class UserCredentials(BaseModel):
    username: Optional[str] = None
    password_file: Optional[Path] = None
    password: Optional[str] = None

    @model_validator(mode="after")
    def read_password(self) -> Self:
        if self.password_file is not None:
            assert self.password_file.is_file(), (
                f"Invalid file path {self.password_file}"
            )

            self.password = self.password_file.read_text().strip()

        return self


def hostname_validator(value: str) -> str:
    pattern = re.compile(
        r"^(?=.{1,255}$)[0-9A-Za-z](?:(?:[0-9A-Za-z]|-){0,61}[0-9A-Za-z])?(?:\.[0-9A-Za-z](?:(?:[0-9A-Za-z]|-){0,6\
1}[0-9A-Za-z])?)*\.?$"
    )

    if not pattern.match(value):
        raise ValueError("Invalid hostname")

    return value


Hostname = Annotated[str, BeforeValidator(hostname_validator)]


class Host(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    hostname: Optional[Hostname] = None
    address: Optional[IPvAnyAddress] = Field(default=IPv4Address("127.0.0.1"))
    port: int

    @field_serializer("address", when_used="always")
    def ip_to_str(self, v: IPvAnyAddress | IPv4Address | IPv6Address) -> str:
        return str(v)

    @model_validator(mode="after")
    def override_hostname(self) -> Self:
        if not self.hostname:
            self.hostname = cast(Hostname, str(self.address))

        return self


class Connection(Host, UserCredentials):
    scheme: Any
    path: Optional[str] = None

    database: Optional[Any] = None

    def to_url(self, credentials: bool = True) -> AnyUrl:
        return AnyUrl.build(
            scheme=self.scheme,
            username=self.username if credentials else None,
            password=self.password if credentials else None,
            host=str(self.hostname),
            port=self.port,
            path=str(self.path).lstrip("/")
            if self.path
            else str(self.database)
            if self.database
            else None,
        )

    def to_string_url(self, credentials: bool = True) -> str:
        return str(self.to_url(credentials))


class HTTPConnection(Connection):
    scheme: Literal["http", "https"] = "http"
    port: int = 8080


class TCPConnection(Connection):
    scheme: Literal["tcp"] = "tcp"
    port: int = 3000


class TaskId(BaseModel):
    id: str


__all__ = [
    "BaseErrorResponse",
    "UserCredentials",
    "Hostname",
    "Host",
    "Connection",
    "HTTPConnection",
    "TCPConnection",
    "TaskId",
]
