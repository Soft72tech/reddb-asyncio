from pathlib import Path
from typing import Literal, Optional, Self

from pydantic import BaseModel, model_validator

from library.core.oauth2.types import GrantType


class OAuth2Config(BaseModel):
    """
    OAuth configuration that stores variable properties.

    Attributes:
        jwt_signing_algo: Algorithm used for JWT signing.
        jwt_signing_key: Key used for signing for the following algorithms - RS256, RS384, RS512, ES256, ES384, ES512, EdDSA.
        jwt_signing_key_file: Path to the file with the key. The value will be read and assigned to `jwt_signing_key` after validation.
        jwt_secret: Secret used for signing for the following algorithms - HS256, HS384, HS512
        jwt_secret_file: Path to the file with the secret. The value will be read and assigned to `jwt_secret` after validation.
        supported_grant_types: List of supported/enabled grant types.
        access_token_lifetime: Lifetime of the token in seconds.
        refresh_token_lifetime: Lifetime of the token in seconds.
    """

    jwt_signing_algo: Literal[
        "HS256",
        "HS384",
        "HS512",
        "RS256",
        "RS384",
        "RS512",
        "ES256",
        "ES384",
        "ES512",
        "EdDSA",
    ] = "HS256"
    jwt_signing_key: Optional[str] = None
    jwt_signing_key_file: Optional[Path] = None
    jwt_secret: str = "jwt_secret_to_change"
    jwt_secret_file: Optional[Path] = None

    supported_grant_types: list[GrantType] = [GrantType.password]

    access_token_lifetime: int = 3600
    refresh_token_lifetime: int = 730 * 60

    cookie_access_token_name: str = "access_token"
    cookie_refresh_token_name: str = "refresh_token"

    @model_validator(mode="after")
    def read_jwt_signing_key(self) -> Self:
        if self.jwt_signing_key_file is not None:
            assert self.jwt_signing_key_file.is_file(), (
                f"Invalid file path {self.jwt_signing_key_file}"
            )

            self.jwt_signing_key = self.jwt_signing_key_file.read_text().strip()

        return self

    @model_validator(mode="after")
    def read_jwt_secret(self) -> Self:
        if self.jwt_secret_file is not None:
            assert self.jwt_secret_file.is_file(), (
                f"Invalid file path {self.jwt_secret_file}"
            )

            self.jwt_secret = self.jwt_secret_file.read_text().strip()

        return self
