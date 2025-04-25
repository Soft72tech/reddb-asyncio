from enum import Enum
from typing import Callable, Optional, Self

from pydantic import BaseModel, ConfigDict
from pydantic_core import ErrorDetails


class TokenType(Enum):
    bearer = "bearer"


class Token(BaseModel):
    """
    Successful Response: https://datatracker.ietf.org/doc/html/rfc6749#section-5.1
    """

    access_token: str
    token_type: TokenType = TokenType.bearer
    expires_in: int
    refresh_token: Optional[str] = None
    scope: Optional[str] = None


class ErrorType(Enum):
    invalid_request = "invalid_request"
    invalid_client = "invalid_client"
    invalid_grant = "invalid_grant"
    unauthorized_client = "unauthorized_client"
    unsupported_grant_type = "unsupported_grant_type"


class Error(BaseModel):
    """
    Error Response: https://datatracker.ietf.org/doc/html/rfc6749#section-5.2
    """

    error: ErrorType
    error_description: Optional[str] = None
    error_uri: Optional[str] = None
    # Extension
    detail: Optional[list[str] | list[ErrorDetails]] = None


class GrantType(Enum):
    authorization_code = "authorization_code"
    implicit = "implicit"
    password = "password"
    client_credentials = "client_credentials"
    refresh_token = "refresh_token"


class AuthorizationGrant(BaseModel):
    """
    Summary of authorization grants used for forms and validations.
    """

    grant_type: GrantType
    username: Optional[str] = None
    password: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    refresh_token: Optional[str] = None
    redirect_uri: Optional[str] = None
    scope: Optional[str] = None
    response_type: Optional[str] = None
    state: Optional[str] = None


class PasswordGrant(BaseModel):
    """
    Resource Owner Password Credentials Grant: https://datatracker.ietf.org/doc/html/rfc6749#section-4.3.2
    """

    username: str
    password: str
    scope: Optional[str] = None


class ClientCredentialsGrant(BaseModel):
    """
    Client Credentials Grant: https://datatracker.ietf.org/doc/html/rfc6749#section-4.4.2
    """

    client_id: str
    client_secret: str
    scope: Optional[str] = None


class RefreshTokenGrant(BaseModel):
    """
    Refresh Token Grant: https://datatracker.ietf.org/doc/html/rfc6749#section-6
    """

    refresh_token: str
    scope: Optional[str] = None


class AuthorizationResponseType(Enum):
    code = "code"


class Authorization(BaseModel):
    """
    Authorization Request: https://datatracker.ietf.org/doc/html/rfc6749#section-4.1.1
    """

    response_type: AuthorizationResponseType = AuthorizationResponseType.code
    client_id: str
    redirect_uri: Optional[str] = None
    scope: Optional[str] = None
    state: Optional[str] = None


class AuthorizationCodeGrant(BaseModel):
    """
    Authorization Code Grant: https://datatracker.ietf.org/doc/html/rfc6749#section-4.1.2
    """

    code: str
    state: Optional[str] = None


def _scope_name_generator(field: str) -> str:
    return ":".join(field.rsplit("_", 1))


class OAuth2ScopesError(Exception): ...


class OAuth2Scopes(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True, alias_generator=_scope_name_generator
    )

    def as_list(self) -> list[str]:
        return [k for k, v in self.model_dump(by_alias=True).items() if v is True]

    def as_dict(self) -> dict[str, bool]:
        return {k: v for k, v in self.model_dump(by_alias=True).items() if v is True}

    def as_descripted_dict(self) -> dict[str, str]:
        return {
            key: field.description or ""
            for field, key in zip(
                list(self.model_fields.values()), list(self.model_dump(by_alias=True))
            )
        }

    def as_str(self, delimiter: str = " ") -> str:
        return delimiter.join(self.as_list())

    def all(self, exclude: Optional[Callable[..., bool]] = None) -> set[str]:
        _all = {k for k, v in self.model_dump(by_alias=True).items()}

        if exclude:
            _all = set(filter(exclude, _all))

        return _all

    @classmethod
    def from_list(cls, scopes: list[str]) -> Self:
        cls._validate_scopes(scopes, list(cls().all()))

        return cls(**{k: True for k in scopes})

    @classmethod
    def from_dict(cls, scopes: dict[str, Optional[bool]]) -> Self:
        cls._validate_scopes(list(scopes.keys()), list(cls().all()))

        return cls(**scopes)

    @classmethod
    def from_str(cls, scopes: str, delimiter: str = " ") -> Self:
        cls._validate_scopes(scopes.split(delimiter), list(cls().all()))

        return cls.from_list(scopes.split(delimiter))

    @staticmethod
    def _validate_scopes(left: list[str], right: list[str]):
        for scope in left:
            if scope not in right:
                raise OAuth2ScopesError("Invalid scope:", scope)

    def validate_scopes(
        self, scopes: Self | list[str] | dict[str, Optional[bool]] | str
    ) -> bool:
        if isinstance(scopes, OAuth2Scopes):
            _scopes = scopes
        elif isinstance(scopes, list):
            _scopes = OAuth2Scopes.from_list(scopes)
        elif isinstance(scopes, dict):
            _scopes = OAuth2Scopes.from_dict(scopes)
        elif isinstance(scopes, str):
            _scopes = OAuth2Scopes.from_str(scopes)
        else:
            raise OAuth2ScopesError(type(scopes), "is not supported")

        for scope in self.as_list():
            if scope not in _scopes.as_list():
                return False
        else:
            return True


class TokenUserSubject(BaseModel):
    username: str
    scope: Optional[str] = None


class TokenAppSubject(BaseModel):
    client_id: str
    scope: Optional[str] = None
