"""
Pydantic models for invite-related requests and responses.
"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class InviteCreate(BaseModel):
    """Request model for creating an invite."""
    team_id: str = Field(..., description="UUID of the team")
    target_role: str = Field(..., pattern="^(player|parent)$", description="Role for invite")
    target_name: Optional[str] = Field(None, max_length=100, description="Pre-filled name")
    linked_player_id: Optional[str] = Field(None, description="For parent invites, the player UUID to link")
    expires_in_days: int = Field(default=30, ge=1, le=365, description="Days until expiration")


class InviteResponse(BaseModel):
    """Response model for invite data."""
    id: str
    code: str
    team_id: str
    target_role: str
    target_name: Optional[str]
    linked_player_id: Optional[str]
    expires_at: datetime
    claimed_by: Optional[str]
    claimed_at: Optional[datetime]
    created_by: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class InvitePreview(BaseModel):
    """Public preview of an invite (for claim page)."""
    code: str
    team_name: str
    target_role: str
    target_name: Optional[str]
    expires_at: datetime
    is_valid: bool
    linked_player_name: Optional[str]  # For parent invites

    class Config:
        from_attributes = True
