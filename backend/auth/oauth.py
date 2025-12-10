"""
Google OAuth utilities for authentication.

Provides functions for Google OAuth flow including URL generation
and token exchange.
"""

import os
from typing import Dict
from urllib.parse import urlencode
import httpx

# Google OAuth configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8080/auth/callback")

# Google OAuth endpoints
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


def get_google_auth_url(state: str = "") -> str:
    """
    Generate Google OAuth authorization URL.

    Args:
        state: Optional state parameter for CSRF protection

    Returns:
        The Google OAuth authorization URL
    """
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
    }

    if state:
        params["state"] = state

    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def exchange_code_for_token(code: str) -> Dict:
    """
    Exchange authorization code for user info.

    Args:
        code: The authorization code from Google OAuth callback

    Returns:
        Dictionary containing user info:
        {
            "email": "user@example.com",
            "name": "User Name",
            "picture": "https://...",
            "verified_email": True
        }

    Raises:
        httpx.HTTPError: If the token exchange fails
        ValueError: If required configuration is missing
    """
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise ValueError("Google OAuth credentials not configured")

    # Exchange code for access token
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        token_response.raise_for_status()
        token_data = token_response.json()

        # Get user info using access token
        access_token = token_data["access_token"]
        userinfo_response = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        userinfo_response.raise_for_status()
        user_info = userinfo_response.json()

        return user_info
