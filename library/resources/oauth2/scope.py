from typing import Optional

from sqlmodel import Field

from library.core.oauth2.types import OAuth2Scopes as _OAuth2Scopes


class OAuth2Scopes(_OAuth2Scopes):
    # specials
    self_read: Optional[bool] = Field(
        default=None, description="Read self (for user only)"
    )
    license_read: Optional[bool] = Field(
        default=None, description="Read license information"
    )
    license_agreement_read: Optional[bool] = Field(
        default=None, description="Read license agreement"
    )
    license_agreement_write: Optional[bool] = Field(
        default=None, description="Write license agreement"
    )

    # resources
    user_read: Optional[bool] = Field(default=None, description="Read user")
    user_write: Optional[bool] = Field(default=None, description="Write user")

    user_role_read: Optional[bool] = Field(default=None, description="Read user role")
    user_role_write: Optional[bool] = Field(default=None, description="Write user role")

    user_audit_read: Optional[bool] = Field(default=None, description="Read user audit")
    user_audit_write: Optional[bool] = Field(
        default=None, description="Write user audit"
    )

    station_read: Optional[bool] = Field(default=None, description="Read station")
    station_write: Optional[bool] = Field(default=None, description="Write station")

    detector_read: Optional[bool] = Field(default=None, description="Read detector")
    detector_write: Optional[bool] = Field(default=None, description="Write detector")

    detector_state_read: Optional[bool] = Field(
        default=None, description="Read detector state"
    )
    detector_state_write: Optional[bool] = Field(
        default=None, description="Write detector state"
    )

    detector_state_history_read: Optional[bool] = Field(
        default=None, description="Read detector state history"
    )
    detector_state_history_write: Optional[bool] = Field(
        default=None, description="Write detector state history"
    )

    camera_read: Optional[bool] = Field(default=None, description="Read camera")
    camera_write: Optional[bool] = Field(default=None, description="Write camera")

    screening_read: Optional[bool] = Field(default=None, description="Read screening")
    screening_write: Optional[bool] = Field(default=None, description="Write screening")

    screening_history_read: Optional[bool] = Field(
        default=None, description="Read screening history"
    )
    screening_history_write: Optional[bool] = Field(
        default=None, description="Write screening history"
    )

    filesystem_read: Optional[bool] = Field(default=None, description="Read filesystem")
    filesystem_write: Optional[bool] = Field(
        default=None, description="Write filesystem"
    )
