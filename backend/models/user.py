"""
Pydantic models for user-related requests and responses.
"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, validator


class GoogleAuthRequest(BaseModel):
    """Request model for Google OAuth authentication."""
    code: str = Field(..., description="Authorization code from Google OAuth")
    state: Optional[str] = Field(None, description="State parameter for CSRF protection")


class UserLogin(BaseModel):
    """Request model for username/password login."""
    username: str = Field(..., min_length=1, description="Username or email")
    password: str = Field(..., min_length=1, description="Password")


class InviteRegisterRequest(BaseModel):
    """Request model for registering via invite code."""
    invite_code: str = Field(..., min_length=1, description="Invite code")
    username: str = Field(..., min_length=3, max_length=50, description="Desired username")
    password: str = Field(..., min_length=8, description="Password (minimum 8 characters)")
    display_name: str = Field(..., min_length=1, max_length=100, description="Display name")
    phone: Optional[str] = Field(None, max_length=20, description="Phone number")

    @validator('username')
    def username_alphanumeric(cls, v):
        """Validate username is alphanumeric (plus underscores and hyphens)."""
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Username must be alphanumeric (underscores and hyphens allowed)')
        return v.lower()

    @validator('password')
    def password_strength(cls, v):
        """Validate password has minimum strength."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v


class UserCreate(BaseModel):
    """Request model for creating a new user (internal use)."""
    email: Optional[EmailStr] = None
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    password: Optional[str] = Field(None, min_length=8)
    display_name: str = Field(..., min_length=1, max_length=100)
    role: str = Field(..., pattern="^(coach|player|parent)$")
    phone: Optional[str] = Field(None, max_length=20)
    auth_provider: str = Field(default="local", pattern="^(local|google)$")


class UserUpdate(BaseModel):
    """Request model for updating user profile."""
    display_name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)


class PasswordChange(BaseModel):
    """Request model for changing password."""
    current_password: str = Field(..., min_length=1, description="Current password")
    new_password: str = Field(..., min_length=8, description="New password (minimum 8 characters)")

    @validator('new_password')
    def password_strength(cls, v):
        """Validate password has minimum strength."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v


class UserResponse(BaseModel):
    """Response model for user data."""
    id: str
    email: Optional[str]
    username: Optional[str]
    display_name: str
    role: str
    phone: Optional[str]
    status: str
    auth_provider: str
    created_at: datetime
    last_login_at: Optional[datetime]

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """Response model for authentication tokens."""
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    user: UserResponse = Field(..., description="User information")


class RefreshTokenRequest(BaseModel):
    """Request model for refreshing access token."""
    refresh_token: str = Field(..., description="Refresh token")
