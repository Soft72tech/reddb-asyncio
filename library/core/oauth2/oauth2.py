import logging
from datetime import timedelta
from functools import partial
from typing import Any, Callable, Coroutine, Optional, cast

from fastapi import status
from fastapi.responses import JSONResponse
from jwt import PyJWTError
from pydantic import ValidationError

from library.core.database.types import AsyncSession

# from library.core.oauth2.application import OAuth2App, OAuth2AppInfo
from library.core.oauth2.config import OAuth2Config
from library.core.oauth2.types import (
    Authorization,
    AuthorizationCodeGrant,
    AuthorizationGrant,
    ClientCredentialsGrant,
    Error,
    ErrorType,
    GrantType,
    OAuth2Scopes,
    PasswordGrant,
    RefreshTokenGrant,
    Token,
    TokenAppSubject,
    TokenUserSubject,
)
from library.core.security.token import create_token, validate_token


async def user_validation(
    password_grant: PasswordGrant, session: AsyncSession
) -> Optional[TokenUserSubject]:
    raise NotImplementedError()


async def user_token_subject_validation(
    subject: TokenUserSubject, session: AsyncSession
) -> bool:
    raise NotImplementedError()


async def app_validation(
    client_credentials_grant: ClientCredentialsGrant, session: AsyncSession
) -> Optional[TokenAppSubject]:
    raise NotImplementedError()


async def app_token_subject_validation(
    subject: TokenAppSubject, session: AsyncSession
) -> bool:
    raise NotImplementedError()


class OAuth2:
    def __init__(
        self,
        config: OAuth2Config,
        scopes: Optional[OAuth2Scopes] = None,
        user_validation: Callable[
            ...,
            Coroutine[Any, Any, Optional[TokenUserSubject]],
        ] = user_validation,
        user_token_subject_validation: Callable[
            ..., Coroutine[Any, Any, bool]
        ] = user_token_subject_validation,
        app_validation: Callable[
            ..., Coroutine[Any, Any, Optional[TokenAppSubject]]
        ] = app_validation,
        app_token_subject_validation: Callable[
            ..., Coroutine[Any, Any, bool]
        ] = app_token_subject_validation,
    ):
        self.config = config
        self.scopes = scopes
        self.user_validation = user_validation
        self.user_token_subject_validation = user_token_subject_validation
        self.app_validation = app_validation
        self.app_token_subject_validation = app_token_subject_validation

    async def _password_grant(
        self, grant: AuthorizationGrant, session: AsyncSession
    ) -> Token | Error:
        """
        Resource Owner Password Credentials Grant: https://datatracker.ietf.org/doc/html/rfc6749#section-4.3
        """
        try:
            _grant = PasswordGrant.model_validate(grant, from_attributes=True)
        except ValidationError as e:
            error = Error(
                error=ErrorType.invalid_request,
                error_description="Invalid request grant",
                detail=e.errors(),
            )
            logging.warning(error)
            return error

        invalid_credentials = Error(
            error=ErrorType.invalid_grant,
            error_description="Invalid username or password",
        )

        if not (token_subject := await self.user_validation(_grant, session)):
            return invalid_credentials

        token = Token(
            access_token=create_token(
                token_subject.model_dump(mode="json"),
                self.config.jwt_secret,
                timedelta(minutes=self.config.access_token_lifetime),
            ),
            expires_in=self.config.access_token_lifetime,
        )

        if GrantType.refresh_token in self.config.supported_grant_types:
            token.refresh_token = create_token(
                token_subject.model_dump(mode="json"),
                self.config.jwt_secret,
                timedelta(minutes=self.config.refresh_token_lifetime),
            )

        if _grant.scope and self.scopes:
            scopes = OAuth2Scopes.from_str(_grant.scope)
            if not self.scopes.validate_scopes(scopes):
                return Error(
                    error=ErrorType.invalid_request,
                    error_description="Invalid request grant",
                    detail=["Unknown grant scopes"]
                    + list(scopes.all() - self.scopes.all()),
                )

        return token

    async def _client_credentials_grant(
        self, grant: AuthorizationGrant, session: AsyncSession
    ) -> Token | Error:
        """
        Client Credentials Grant: https://datatracker.ietf.org/doc/html/rfc6749#section-4.4
        """
        try:
            _grant = ClientCredentialsGrant.model_validate(grant, from_attributes=True)
        except ValidationError as e:
            error = Error(
                error=ErrorType.invalid_request,
                error_description="Invalid request grant",
                detail=e.errors(),
            )
            logging.warning(error)
            return error

        invalid_credentials = Error(
            error=ErrorType.invalid_grant,
            error_description="Invalid client ID or client secret",
        )

        if not (token_subject := await self.app_validation(_grant, session)):
            return invalid_credentials

        token = Token(
            access_token=create_token(
                token_subject.model_dump(mode="json"),
                self.config.jwt_secret,
                timedelta(minutes=self.config.access_token_lifetime),
            ),
            expires_in=self.config.access_token_lifetime,
        )

        if GrantType.refresh_token in self.config.supported_grant_types:
            token.refresh_token = create_token(
                token_subject.model_dump(mode="json"),
                self.config.jwt_secret,
                timedelta(minutes=self.config.refresh_token_lifetime),
            )

        if _grant.scope and self.scopes:
            scopes = OAuth2Scopes.from_str(_grant.scope)
            if not self.scopes.validate_scopes(scopes):
                return Error(
                    error=ErrorType.invalid_request,
                    error_description="Invalid request grant",
                    detail=["Unknown grant scopes"]
                    + list(
                        scopes.all()
                        - self.scopes.all(exclude=lambda v: v.startswith("self"))
                    ),
                )

        return token

    async def _refresh_token_grant(
        self, grant: AuthorizationGrant, session: AsyncSession
    ) -> Token | Error:
        """
        Client Credentials Grant: https://datatracker.ietf.org/doc/html/rfc6749#section-4.4
        """
        try:
            _grant = RefreshTokenGrant.model_validate(grant, from_attributes=True)
        except ValidationError as e:
            return Error(
                error=ErrorType.invalid_request,
                error_description="Invalid request grant",
                detail=e.errors(),
            )

        invalid_credentials = Error(
            error=ErrorType.invalid_grant,
            error_description="Invalid refresh token",
        )

        try:
            token_claims = validate_token(_grant.refresh_token, self.config.jwt_secret)
        except PyJWTError:
            return invalid_credentials

        if token_claims.sub is None or token_claims.sub == {}:
            return invalid_credentials

        valid_refresh_token = False

        try:
            token_subject = TokenUserSubject(**token_claims.sub)
            valid_refresh_token = await self.user_token_subject_validation(
                token_subject, session
            )

        except ValidationError:
            pass

        try:
            if not valid_refresh_token:
                token_subject = TokenAppSubject(**token_claims.sub)
                valid_refresh_token = await self.app_token_subject_validation(
                    token_subject, session
                )

        except ValidationError:
            pass

        if not valid_refresh_token:
            return invalid_credentials

        token = Token(
            access_token=create_token(
                token_subject.model_dump(mode="json"),
                self.config.jwt_secret,
                timedelta(minutes=self.config.access_token_lifetime),
            ),
            expires_in=self.config.access_token_lifetime,
            refresh_token=_grant.refresh_token,
        )

        if _grant.scope:
            pass

        return token

    async def _authorization_code_grant(
        self, grant: AuthorizationGrant, session: AsyncSession
    ) -> Token | Error:
        _ = AuthorizationCodeGrant.model_validate(grant)
        raise NotImplementedError()

    async def authorize(self, authorization: Authorization, session: AsyncSession):
        # TODO: prevent authorization with Authorization header and return 401
        raise NotImplementedError()

    async def token(
        self, grant: AuthorizationGrant, session: AsyncSession
    ) -> JSONResponse:
        unsupported_grant_type = Error(
            error=ErrorType.unsupported_grant_type,
            error_description=f"Grant type '{grant.grant_type.name}' is not supported. Supported grant types: {[grant_type.name for grant_type in self.config.supported_grant_types]}",
        ).model_dump(mode="json")

        headers = {"Cache-Control": "no-store", "Pragma": "no-cache"}
        success_response = partial(
            JSONResponse, status_code=status.HTTP_200_OK, headers=headers
        )
        error_response = partial(
            JSONResponse, status_code=status.HTTP_400_BAD_REQUEST, headers=headers
        )

        if grant.grant_type not in self.config.supported_grant_types:
            return error_response(unsupported_grant_type)

        match grant.grant_type:
            case GrantType.password:
                result = await self._password_grant(grant, session)
            case GrantType.client_credentials:
                result = await self._client_credentials_grant(grant, session)
            case GrantType.refresh_token:
                result = await self._refresh_token_grant(grant, session)
            case GrantType.authorization_code:
                return error_response(unsupported_grant_type)
                result = await self._authorization_code_grant(grant, session)
            case _:
                return error_response(unsupported_grant_type)

        if isinstance(result, Error):
            return error_response(cast(Error, result).model_dump(mode="json"))

        return success_response(cast(Token, result).model_dump(mode="json"))
