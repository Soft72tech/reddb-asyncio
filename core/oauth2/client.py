import logging
from typing import AsyncGenerator, Optional, cast

from fastapi import status
from httpx import AsyncClient, Auth, HTTPStatusError, Request, Response

from library.core.oauth2.types import (
    AuthorizationGrant,
    ClientCredentialsGrant,
    GrantType,
    Token,
)


class ClientCredentialsAuth(Auth):
    requires_response_body = True

    def __init__(self, token_url: str, credentials: ClientCredentialsGrant):
        self.token_url = token_url
        self.credentials = credentials
        self.token: Optional[Token] = None

    async def _request_client_credentials_grant(self) -> Optional[Token]:
        async with AsyncClient() as client:
            credentials = AuthorizationGrant(
                grant_type=GrantType.client_credentials, **self.credentials.model_dump()
            )
            response = await client.post(
                self.token_url, data=credentials.model_dump(mode="json")
            )

            try:
                response.raise_for_status()
            except HTTPStatusError as e:
                logging.error(f"{e.args}")
                return

            return Token(**response.json())

    async def _request_refresh_token_grant(self) -> Optional[Token]:
        async with AsyncClient() as client:
            credentials = AuthorizationGrant(
                grant_type=GrantType.refresh_token,
                refresh_token=cast(Token, self.token).refresh_token,
            )
            response = await client.post(
                self.token_url,
                data=credentials.model_dump(mode="json"),
            )

            try:
                response.raise_for_status()
            except HTTPStatusError as e:
                logging.error(f"{e.args}")
                return

            return Token(**response.json())

    async def async_auth_flow(
        self, request: Request
    ) -> AsyncGenerator[Request, Response]:
        if not self.token:
            self.token = await self._request_client_credentials_grant()

        if self.token:
            request.headers["Authorization"] = f"Bearer {self.token.access_token}"

        response = yield request

        if (
            cast(Response, response).status_code == status.HTTP_401_UNAUTHORIZED
            and self.token
            and self.token.refresh_token
        ):
            self.token = await self._request_refresh_token_grant()

            if self.token:
                request.headers["Authorization"] = f"Bearer {self.token.access_token}"
            yield request
