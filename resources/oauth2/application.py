from typing import Optional, Self, cast
from uuid import UUID

from pydantic import ConfigDict
from sqlalchemy import select
from sqlmodel import Field, Relationship, SQLModel
from sqlmodel.main import SQLModelConfig

from library.core.database.types import GUID, AsyncSession
from library.core.models import AuditModel, UUIDModel
from library.core.security.password import hash_password, validate_password
from library.resources.oauth2.scope import OAuth2Scopes


class OAuth2ApplicationBase(SQLModel):
    client_id: str = Field(index=True, unique=True)  # TODO: should be generated?
    client_name: str
    redirect_uri: Optional[str] = None
    confidential_client: bool = False

    oauth2_grant_uuid: Optional[UUID] = Field(
        default=None,
        foreign_key="oauth2_grants.uuid",
        nullable=True,
        sa_type=GUID,
    )


class OAuth2ApplicationPrivate(OAuth2ApplicationBase):
    hashed_client_secret: str


class OAuth2ApplicationPublic(OAuth2ApplicationBase, AuditModel):
    model_config = cast(SQLModelConfig, ConfigDict(from_attributes=True))

    uuid: UUID


class OAuth2ApplicationCreate(OAuth2ApplicationBase):
    client_secret: str


class OAuth2Application(UUIDModel, AuditModel, OAuth2ApplicationPrivate, table=True):
    __tablename__ = "oauth2_applications"  # type: ignore

    oauth2_grant: "OAuth2Grant" = Relationship(back_populates="oauth2_application")

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

    @classmethod
    async def with_uuid(cls, session: AsyncSession, uuid: UUID) -> Optional[Self]:
        return await session.scalar(select(cls).where(cls.uuid == uuid))

    @classmethod
    async def new(
        cls, session: AsyncSession, oauth2_application_data: OAuth2ApplicationCreate
    ) -> Self:
        oauth2_application = OAuth2Application(
            hashed_client_secret=hash_password(oauth2_application_data.client_secret),
            **OAuth2ApplicationBase.model_validate(
                oauth2_application_data
            ).model_dump(),
        )

        return await oauth2_application.create(session)  # type:ignore

    async def public(self, session: AsyncSession) -> OAuth2ApplicationPublic:
        session.add(self)
        await session.refresh(self, attribute_names=["oauth2_grant"])

        return OAuth2ApplicationPublic.model_validate(self)

    def validate_secret(self, client_secret: str) -> bool:
        return validate_password(client_secret, self.hashed_client_secret)

    async def remove_grant(self, session: AsyncSession) -> Self:
        session.add(self)
        await session.refresh(self, attribute_names=["oauth2_grant"])

        if self.oauth2_grant:
            await self.oauth2_grant.remove(session)
            self.oauth2_grant_uuid = None

        self.refresh_updated_at()
        await session.flush()

        return self

    async def refresh_grant(
        self, session: AsyncSession, scopes: Optional[list[str]]
    ) -> Self:
        if scopes is None:
            return await self.remove_grant(session)

        oauth2_scopes = OAuth2Scopes.from_list(scopes).as_str()

        session.add(self)
        await session.refresh(self, attribute_names=["oauth2_grant"])

        if not self.oauth2_grant:
            oauth2_grant = await OAuth2Grant(scopes=oauth2_scopes).create(session)
            self.oauth2_grant_uuid = oauth2_grant.uuid

        else:
            await self.oauth2_grant.refresh_scopes(session, scopes)

        self.refresh_updated_at()
        await session.flush()

        return self


from library.resources.oauth2.grant import OAuth2Grant  # noqa: E402
