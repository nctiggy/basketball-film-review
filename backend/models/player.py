"""
Pydantic models for player-specific requests and responses.
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


class PlayerClipResponse(BaseModel):
    """Response model for clips assigned to a player."""
    id: str
    game_id: str
    video_id: str
    start_time: str
    end_time: str
    tags: List[str]
    players: List[str]
    notes: Optional[str]
    clip_path: Optional[str]
    status: str
    created_at: datetime

    # Assignment-specific fields
    assignment_id: str
    assigned_by_id: str
    assigned_by_name: str
    message: Optional[str]
    priority: str
    viewed_at: Optional[datetime]
    acknowledged_at: Optional[datetime]
    assignment_created_at: datetime

    # Game info for context
    game_name: str
    game_date: str

    class Config:
        from_attributes = True


class PlayerStatsResponse(BaseModel):
    """Response model for player statistics."""
    game_id: str
    game_name: str
    game_date: str
    points: int
    field_goals_made: int
    field_goals_attempted: int
    three_pointers_made: int
    three_pointers_attempted: int
    free_throws_made: int
    free_throws_attempted: int
    offensive_rebounds: int
    defensive_rebounds: int
    assists: int
    steals: int
    blocks: int
    turnovers: int
    fouls: int
    minutes_played: Optional[int]
    recorded_at: datetime

    class Config:
        from_attributes = True


class PlayerTeamResponse(BaseModel):
    """Response model for teams a player is on."""
    id: str
    name: str
    season: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class SeasonStatsResponse(BaseModel):
    """Response model for aggregated season statistics."""
    games_played: int
    avg_points: float
    avg_rebounds: float
    avg_assists: float
    fg_percentage: float
    three_pt_percentage: float
    ft_percentage: float

    class Config:
        from_attributes = True
