"""
Pydantic models for request/response validation.
"""

from .user import (
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdate,
    PasswordChange,
    TokenResponse,
    GoogleAuthRequest,
    InviteRegisterRequest
)

from .team import (
    TeamCreate,
    TeamUpdate,
    TeamResponse,
    CoachResponse,
    AddCoachRequest,
    RosterPlayerResponse,
    AddPlayerRequest
)

from .invite import (
    InviteCreate,
    InviteResponse,
    InvitePreview
)

from .assignment import (
    ClipAssignRequest,
    ClipAssignmentResponse
)

from .annotation import (
    AnnotationData,
    AnnotationResponse
)

from .stats import (
    PlayerGameStats,
    GameStatsRequest,
    PlayerStatsResponse,
    TeamStatsResponse,
    GameStatsResponse
)

__all__ = [
    # User models
    "UserCreate",
    "UserLogin",
    "UserResponse",
    "UserUpdate",
    "PasswordChange",
    "TokenResponse",
    "GoogleAuthRequest",
    "InviteRegisterRequest",

    # Team models
    "TeamCreate",
    "TeamUpdate",
    "TeamResponse",
    "CoachResponse",
    "AddCoachRequest",
    "RosterPlayerResponse",
    "AddPlayerRequest",

    # Invite models
    "InviteCreate",
    "InviteResponse",
    "InvitePreview",

    # Assignment models
    "ClipAssignRequest",
    "ClipAssignmentResponse",

    # Annotation models
    "AnnotationData",
    "AnnotationResponse",

    # Stats models
    "PlayerGameStats",
    "GameStatsRequest",
    "PlayerStatsResponse",
    "TeamStatsResponse",
    "GameStatsResponse"
]
