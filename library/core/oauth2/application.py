# class OAuth2App(UUIDModel, AuditModel, table=True):
#     __tablename__ = "oauth2_apps"

#     # Client details
#     client_id: str = Field(index=True, unique=True)
#     hashed_client_secret: str
#     client_name: str
#     redirect_uri: Optional[str]
#     confidential_client: bool

#     # Relationships
#     grants: list["OAuth2Grant"] = Relationship(back_populates="app")

#     @classmethod
#     async def by_client_id(cls, client_id: str, session) -> Optional[Self]:
#         return (
#             await session.scalars(select(cls).where(cls.client_id == client_id))
#         ).first()

#     @classmethod
#     def with_credentials(
#         cls,
#         client_name: str,
#         client_id: Optional[str] = None,
#         client_secret: Optional[str] = None,
#         redirect_uri: Optional[str] = None,
#         confidential_client: bool = False,
#     ) -> Self:
#         client_id = client_id or Sqids(min_length=16).encode([id(cls), int(time())])
#         client_secret = client_secret or SecretKey.create().decode()

#         return cls(
#             client_id=client_id,
#             hashed_client_secret=hash_password(client_secret),
#             client_name=client_name,
#             redirect_uri=redirect_uri,
#             confidential_client=confidential_client,
#         )

#     def validate_secret(self, client_secret: str) -> bool:
#         return validate_password(client_secret, self.hashed_client_secret)


# class OAuth2AppInfo(SQLModel):
#     client_id: str
#     client_name: str


# class OAuth2AppNew(BaseModel):
#     client_id: str
#     client_secret: str
#     client_name: str
#     redirect_uri: Optional[str]
#     confidential_client: bool = False


# class OAuth2Grant(IdModel, AuditModel, table=True):
#     __tablename__ = "oauth2_grants"

#     app_id: Optional[UUID] = Field(default=None, foreign_key="oauth2_apps.id")
#     app: OAuth2App = Relationship(back_populates="grants")

#     user_id: Optional[UUID] = Field(default=None, foreign_key="users.id")
#     user: Type[BaseUser] = Relationship(back_populates="oauth2_grant")

#     scopes: str
