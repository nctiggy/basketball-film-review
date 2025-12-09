"""
Authentication module for Basketball Film Review.

This module provides authentication and authorization functionality including:
- JWT token generation and validation
- Password hashing and verification
- Google OAuth integration
- FastAPI dependencies for route protection
"""

from .jwt import create_access_token, create_refresh_token, decode_token
from .password import hash_password, verify_password
from .oauth import get_google_auth_url, exchange_code_for_token
from .dependencies import (
    get_current_user,
    get_current_user_optional,
    require_role,
    require_coach,
    require_team_access
)

__all__ = [
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "hash_password",
    "verify_password",
    "get_google_auth_url",
    "exchange_code_for_token",
    "get_current_user",
    "get_current_user_optional",
    "require_role",
    "require_coach",
    "require_team_access",
]
