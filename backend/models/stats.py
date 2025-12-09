"""
Pydantic models for player stats-related requests and responses.
"""

from typing import Optional, List, Dict
from datetime import datetime
from pydantic import BaseModel, Field


class PlayerGameStats(BaseModel):
    """Request/Response model for player game statistics."""
    player_id: str = Field(..., description="Player UUID")
    player_name: Optional[str] = Field(None, description="Player name (response only)")

    # Scoring
    points: int = Field(default=0, ge=0, description="Total points")
    field_goals_made: int = Field(default=0, ge=0, description="Field goals made")
    field_goals_attempted: int = Field(default=0, ge=0, description="Field goals attempted")
    three_pointers_made: int = Field(default=0, ge=0, description="Three-pointers made")
    three_pointers_attempted: int = Field(default=0, ge=0, description="Three-pointers attempted")
    free_throws_made: int = Field(default=0, ge=0, description="Free throws made")
    free_throws_attempted: int = Field(default=0, ge=0, description="Free throws attempted")

    # Rebounds
    offensive_rebounds: int = Field(default=0, ge=0, description="Offensive rebounds")
    defensive_rebounds: int = Field(default=0, ge=0, description="Defensive rebounds")

    # Other stats
    assists: int = Field(default=0, ge=0, description="Assists")
    steals: int = Field(default=0, ge=0, description="Steals")
    blocks: int = Field(default=0, ge=0, description="Blocks")
    turnovers: int = Field(default=0, ge=0, description="Turnovers")
    fouls: int = Field(default=0, ge=0, description="Personal fouls")
    minutes_played: Optional[int] = Field(None, ge=0, description="Minutes played")

    class Config:
        from_attributes = True


class GameStatsRequest(BaseModel):
    """Request model for adding/updating game stats."""
    stats: List[PlayerGameStats] = Field(..., min_items=1, description="List of player stats")


class PlayerStatsResponse(BaseModel):
    """Response model for a player's stats across games."""
    player_id: str
    player_name: str
    games_played: int
    total_points: int
    total_rebounds: int
    total_assists: int
    avg_points: float
    avg_rebounds: float
    avg_assists: float
    fg_percentage: Optional[float]
    three_pt_percentage: Optional[float]
    ft_percentage: Optional[float]

    class Config:
        from_attributes = True


class TeamStatsResponse(BaseModel):
    """Response model for team aggregate stats."""
    team_id: str
    team_name: str
    total_games: int
    player_stats: List[PlayerStatsResponse]

    class Config:
        from_attributes = True


class GameStatsResponse(BaseModel):
    """Response model for all stats in a game."""
    game_id: str
    game_name: str
    stats: List[PlayerGameStats]

    class Config:
        from_attributes = True
