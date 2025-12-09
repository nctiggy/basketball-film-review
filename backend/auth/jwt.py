"""
JWT token utilities for authentication.

Provides functions for creating and decoding JWT tokens using HS256 algorithm.
"""

import os
from datetime import datetime, timedelta
from typing import Dict, Optional
import jwt
from jwt.exceptions import InvalidTokenError

# Configuration from environment
JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_DAYS", "7"))


def create_access_token(user_id: str, role: str, additional_claims: Optional[Dict] = None) -> str:
    """
    Create a JWT access token.

    Args:
        user_id: The user's UUID as a string
        role: The user's role ('coach', 'player', 'parent')
        additional_claims: Optional additional claims to include in the token

    Returns:
        Encoded JWT token string
    """
    expires_delta = timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    expire = datetime.utcnow() + expires_delta

    payload = {
        "sub": user_id,  # Subject (user ID)
        "role": role,
        "type": "access",
        "exp": expire,
        "iat": datetime.utcnow()
    }

    if additional_claims:
        payload.update(additional_claims)

    encoded_jwt = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def create_refresh_token(user_id: str) -> str:
    """
    Create a JWT refresh token.

    Args:
        user_id: The user's UUID as a string

    Returns:
        Encoded JWT refresh token string
    """
    expires_delta = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    expire = datetime.utcnow() + expires_delta

    payload = {
        "sub": user_id,
        "type": "refresh",
        "exp": expire,
        "iat": datetime.utcnow()
    }

    encoded_jwt = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Dict:
    """
    Decode and validate a JWT token.

    Args:
        token: The JWT token string to decode

    Returns:
        Dictionary containing the token payload

    Raises:
        InvalidTokenError: If the token is invalid or expired
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except InvalidTokenError as e:
        raise InvalidTokenError(f"Invalid token: {str(e)}")
