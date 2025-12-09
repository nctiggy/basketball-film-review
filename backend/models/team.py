"""
Pydantic models for team-related requests and responses.
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


class TeamCreate(BaseModel):
    """Request model for creating a team."""
    name: str = Field(..., min_length=1, max_length=100, description="Team name")
    season: Optional[str] = Field(None, max_length=50, description="Season (e.g., '2024-2025')")


class TeamUpdate(BaseModel):
    """Request model for updating a team."""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Team name")
    season: Optional[str] = Field(None, max_length=50, description="Season")


class TeamResponse(BaseModel):
    """Response model for team data."""
    id: str
    name: str
    season: Optional[str]
    created_by: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class CoachResponse(BaseModel):
    """Response model for coach in team context."""
    id: str
    display_name: str
    email: Optional[str]
    role: str  # 'head' or 'assistant'
    added_at: datetime

    class Config:
        from_attributes = True


class AddCoachRequest(BaseModel):
    """Request model for adding a coach to a team."""
    coach_id: str = Field(..., description="UUID of the coach to add")
    role: str = Field(default="assistant", pattern="^(head|assistant)$", description="Coach role")


class RosterPlayerResponse(BaseModel):
    """Response model for player in roster context."""
    id: str
    display_name: str
    username: Optional[str]
    jersey_number: Optional[str]
    position: Optional[str]
    graduation_year: Optional[int]
    status: str
    added_at: datetime

    class Config:
        from_attributes = True


class AddPlayerRequest(BaseModel):
    """Request model for adding a player to a team (creates user and invite)."""
    display_name: str = Field(..., min_length=1, max_length=100, description="Player's full name")
    jersey_number: Optional[str] = Field(None, max_length=10, description="Jersey number")
    position: Optional[str] = Field(None, pattern="^(PG|SG|SF|PF|C)?$", description="Position")
    graduation_year: Optional[int] = Field(None, ge=2020, le=2040, description="Graduation year")
