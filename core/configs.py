from pathlib import Path
from typing import Literal, Optional, Self

from pydantic import BaseModel, NameEmail, model_validator

from library.core.types import Connection


class CacheConfig(Connection): ...


class RedisConfig(CacheConfig):
    scheme: Literal["redis", "rediss"] = "redis"
    database: Optional[int] = 1
    port: int = 6379


class DatabaseConfig(Connection):
    enable_migrations: bool = False


class PostgresConfig(DatabaseConfig):
    scheme: Literal["postgresql", "postgresql+asyncpg", "postgresql+psycopg"] = (
        "postgresql+psycopg"
    )
    database: str = "postgres"
    port: int = 5432
    username: Optional[str] = "postgres"


class SMTPConfig(Connection):
    scheme: Literal["smtp", "smtps", "smtp+starttls"] = "smtp+starttls"
    port: int = 587
    cert_file: Optional[Path] = None
    key_file: Optional[Path] = None


class MailerConfig(BaseModel):
    connection: SMTPConfig = SMTPConfig()
    from_name: Optional[NameEmail] = None


class SecurityConfig(BaseModel):
    secret_key: Optional[str] = None
    secret_key_file: Optional[Path] = None

    password_min_length: int = 8
    password_hash_algo: Literal["bcrypt"] = "bcrypt"
    password_reset_token_lifetime: int = 172800

    cookie_secure: bool = True
    cookie_http_only: bool = True
    cookie_access_token_name: str = "access_token"
    cookie_refresh_token_name: str = "refresh_token"

    cors_allow_origins: list[str] = []
    cors_allow_methods: list[str] = ["*"]
    cors_allow_headers: list[str] = ["*"]
    cors_allow_credentials: bool = True

    @model_validator(mode="after")
    def read_secret_key(self) -> Self:
        if self.secret_key_file is not None:
            assert self.secret_key_file.is_file(), (
                f"Invalid file path {self.secret_key_file}"
            )

            self.secret_key = self.secret_key_file.read_text().strip()

        return self
