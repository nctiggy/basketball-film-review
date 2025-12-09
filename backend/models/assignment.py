"""
Pydantic models for clip assignment-related requests and responses.
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


class ClipAssignRequest(BaseModel):
    """Request model for assigning a clip to player(s)."""
    player_ids: List[str] = Field(..., min_items=1, description="List of player UUIDs to assign to")
    message: Optional[str] = Field(None, max_length=500, description="Message to players about this clip")
    priority: str = Field(default="normal", pattern="^(high|normal|low)$", description="Priority level")


class ClipAssignmentResponse(BaseModel):
    """Response model for clip assignment data."""
    id: str
    clip_id: str
    player_id: str
    player_name: str
    assigned_by: Optional[str]
    message: Optional[str]
    priority: str
    viewed_at: Optional[datetime]
    acknowledged_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True
