from typing import Optional, Self

from sqlmodel import Field, Relationship

from library.core.database.types import AsyncSession
from library.core.models import AuditModel, UUIDModel
from library.resources.oauth2.scope import OAuth2Scopes


class OAuth2GrantError(Exception): ...


class OAuth2Grant(UUIDModel, AuditModel, table=True):
    __tablename__ = "oauth2_grants"  # type: ignore

    oauth2_application: "OAuth2Application" = Relationship(
        back_populates="oauth2_grant",
    )

    user_role: "UserRole" = Relationship(
        back_populates="oauth2_grant",
    )

    # required, no scopes is equal no grant
    scopes: str = Field(nullable=False)

    async def create(self, session: AsyncSession) -> Self:
        session.add(self)
        await session.flush()

        return self

    async def remove(self, session: AsyncSession) -> Self:
        await session.delete(self)
        await session.flush()

        return self

    async def refresh(self, session: AsyncSession) -> Self:
        self.refresh_updated_at()

        session.add(self)
        await session.flush()

        return self

    def validate_scopes(
        self,
        scopes: OAuth2Scopes | list[str] | dict[str, Optional[bool]] | str,
        delimiter: str = " ",
    ) -> bool:
        return OAuth2Scopes.from_str(
            scopes=self.scopes, delimiter=delimiter
        ).validate_scopes(scopes=scopes)

    async def refresh_scopes(self, session: AsyncSession, scopes: list[str]) -> Self:
        self.scopes = OAuth2Scopes.from_list(scopes).as_str()

        session.add(self)
        self.refresh_updated_at()
        await session.flush()

        return self


from library.resources.oauth2.application import OAuth2Application  # noqa: E402
from library.resources.user.roles import UserRole  # noqa: E402
