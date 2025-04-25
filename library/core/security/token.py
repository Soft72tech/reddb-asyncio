from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt

# from jose import jwt
from pydantic import AnyUrl, BaseModel


class TokenClaims(BaseModel):
    """Registered Claim of JWT.

    https://datatracker.ietf.org/doc/html/rfc7519

    Args:
        sub: The "sub" (subject) claim identifies the principal that is the subject of the JWT.
        iat: The "iat" (issued at) claim identifies the time at which the JWT was issued.
        exp: The "exp" (expiration time) claim identifies the expiration time on or after which the JWT MUST NOT be accepted for processing.
        iss: The "iss" (issuer) claim identifies the principal that issued the JWT.
        aud: The "aud" (audience) claim identifies the recipients that the JWT is intended for.
    """

    sub: dict[str, Any] = {}
    iat: float
    exp: float
    iss: Optional[str | AnyUrl] = None
    aud: Optional[list[str | AnyUrl]] = None


def create_token(
    subject: dict[str, Any],
    secret_key: str,
    expires_delta: Optional[timedelta] = timedelta(minutes=15),
    issuer: Optional[str | AnyUrl] = None,
    audience: Optional[list[str | AnyUrl]] = None,
    algorithm: str = "HS256",
) -> str:
    now = datetime.now(timezone.utc)

    if expires_delta is None:
        expires_delta = timedelta(minutes=15)

    claims = TokenClaims(
        sub=subject.copy(),
        iat=now.timestamp(),
        exp=(now + expires_delta).timestamp(),
        iss=issuer,
        aud=audience,
    )

    return jwt.encode(
        payload=claims.model_dump(mode="json"),
        key=secret_key,
        algorithm=algorithm,
    )


def validate_token(
    token: str,
    secret_key: str,
    issuer: Optional[str] = None,
    audience: Optional[list[str]] = None,
    algorithm: str = "HS256",
) -> TokenClaims:
    mapping = jwt.decode(
        jwt=token,
        key=secret_key,
        algorithms=[algorithm],
        issuer=issuer,
        audience=audience,
        verify=True,
        options={"verify_sub": False},
    )
    claims = TokenClaims.model_validate(mapping)

    return claims
