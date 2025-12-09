"""
Parent-specific routes.

Provides endpoints for parents to:
- View their linked children
- View clips assigned to their children
- View their children's stats
"""

from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
import uuid

from backend.models.parent import ChildResponse
from backend.models.player import PlayerClipResponse, PlayerStatsResponse, SeasonStatsResponse
from backend.auth import get_current_user
from backend.auth.dependencies import db_pool

router = APIRouter(prefix="/me", tags=["Parent"])


@router.get("/children", response_model=List[ChildResponse])
async def get_my_children(current_user: dict = Depends(get_current_user)):
    """
    Get all children linked to the current parent.

    Only accessible by parents.
    """
    if current_user["role"] != "parent":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only parents can access this endpoint"
        )

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                u.id,
                u.username,
                u.display_name,
                u.phone,
                pl.verified_at as linked_at,
                pp.jersey_number,
                pp.position,
                pp.graduation_year
            FROM users u
            INNER JOIN parent_links pl ON u.id = pl.player_id
            LEFT JOIN player_profiles pp ON u.id = pp.user_id
            WHERE pl.parent_id = $1
            ORDER BY u.display_name
            """,
            uuid.UUID(current_user["id"])
        )

    return [
        ChildResponse(
            id=str(row["id"]),
            username=row["username"],
            display_name=row["display_name"],
            phone=row["phone"],
            linked_at=row["linked_at"],
            jersey_number=row["jersey_number"],
            position=row["position"],
            graduation_year=row["graduation_year"]
        )
        for row in rows
    ]


@router.get("/children/{child_id}/clips", response_model=List[PlayerClipResponse])
async def get_child_clips(child_id: str, current_user: dict = Depends(get_current_user)):
    """
    Get all clips assigned to a specific child.

    Only accessible by parents linked to that child.
    """
    if current_user["role"] != "parent":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only parents can access this endpoint"
        )

    async with db_pool.acquire() as conn:
        # Verify this child is linked to this parent
        is_linked = await conn.fetchval(
            """
            SELECT EXISTS(
                SELECT 1 FROM parent_links
                WHERE parent_id = $1 AND player_id = $2
            )
            """,
            uuid.UUID(current_user["id"]),
            uuid.UUID(child_id)
        )

        if not is_linked:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This child is not linked to your account"
            )

        # Get clips assigned to the child
        rows = await conn.fetch(
            """
            SELECT
                c.id,
                c.game_id,
                c.video_id,
                c.start_time,
                c.end_time,
                c.tags,
                c.players,
                c.notes,
                c.clip_path,
                c.status,
                c.created_at,
                ca.id as assignment_id,
                ca.assigned_by as assigned_by_id,
                u.display_name as assigned_by_name,
                ca.message,
                ca.priority,
                ca.viewed_at,
                ca.acknowledged_at,
                ca.created_at as assignment_created_at,
                g.name as game_name,
                g.date as game_date
            FROM clips c
            INNER JOIN clip_assignments ca ON c.id = ca.clip_id
            INNER JOIN users u ON ca.assigned_by = u.id
            INNER JOIN games g ON c.game_id = g.id
            WHERE ca.player_id = $1
            ORDER BY ca.viewed_at IS NULL DESC, ca.created_at DESC
            """,
            uuid.UUID(child_id)
        )

    return [
        PlayerClipResponse(
            id=str(row["id"]),
            game_id=str(row["game_id"]),
            video_id=str(row["video_id"]),
            start_time=row["start_time"],
            end_time=row["end_time"],
            tags=row["tags"],
            players=row["players"],
            notes=row["notes"],
            clip_path=row["clip_path"],
            status=row["status"],
            created_at=row["created_at"],
            assignment_id=str(row["assignment_id"]),
            assigned_by_id=str(row["assigned_by_id"]),
            assigned_by_name=row["assigned_by_name"],
            message=row["message"],
            priority=row["priority"],
            viewed_at=row["viewed_at"],
            acknowledged_at=row["acknowledged_at"],
            assignment_created_at=row["assignment_created_at"],
            game_name=row["game_name"],
            game_date=str(row["game_date"])
        )
        for row in rows
    ]


@router.get("/children/{child_id}/stats", response_model=List[PlayerStatsResponse])
async def get_child_stats(child_id: str, current_user: dict = Depends(get_current_user)):
    """
    Get all game stats for a specific child.

    Only accessible by parents linked to that child.
    """
    if current_user["role"] != "parent":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only parents can access this endpoint"
        )

    async with db_pool.acquire() as conn:
        # Verify this child is linked to this parent
        is_linked = await conn.fetchval(
            """
            SELECT EXISTS(
                SELECT 1 FROM parent_links
                WHERE parent_id = $1 AND player_id = $2
            )
            """,
            uuid.UUID(current_user["id"]),
            uuid.UUID(child_id)
        )

        if not is_linked:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This child is not linked to your account"
            )

        # Get stats for the child
        rows = await conn.fetch(
            """
            SELECT
                pgs.game_id,
                g.name as game_name,
                g.date as game_date,
                pgs.points,
                pgs.field_goals_made,
                pgs.field_goals_attempted,
                pgs.three_pointers_made,
                pgs.three_pointers_attempted,
                pgs.free_throws_made,
                pgs.free_throws_attempted,
                pgs.offensive_rebounds,
                pgs.defensive_rebounds,
                pgs.assists,
                pgs.steals,
                pgs.blocks,
                pgs.turnovers,
                pgs.fouls,
                pgs.minutes_played,
                pgs.created_at as recorded_at
            FROM player_game_stats pgs
            INNER JOIN games g ON pgs.game_id = g.id
            WHERE pgs.player_id = $1
            ORDER BY g.date DESC
            """,
            uuid.UUID(child_id)
        )

    return [
        PlayerStatsResponse(
            game_id=str(row["game_id"]),
            game_name=row["game_name"],
            game_date=str(row["game_date"]),
            points=row["points"],
            field_goals_made=row["field_goals_made"],
            field_goals_attempted=row["field_goals_attempted"],
            three_pointers_made=row["three_pointers_made"],
            three_pointers_attempted=row["three_pointers_attempted"],
            free_throws_made=row["free_throws_made"],
            free_throws_attempted=row["free_throws_attempted"],
            offensive_rebounds=row["offensive_rebounds"],
            defensive_rebounds=row["defensive_rebounds"],
            assists=row["assists"],
            steals=row["steals"],
            blocks=row["blocks"],
            turnovers=row["turnovers"],
            fouls=row["fouls"],
            minutes_played=row["minutes_played"],
            recorded_at=row["recorded_at"]
        )
        for row in rows
    ]


@router.get("/children/{child_id}/stats/season", response_model=SeasonStatsResponse)
async def get_child_season_stats(child_id: str, current_user: dict = Depends(get_current_user)):
    """
    Get aggregated season statistics for a specific child.

    Only accessible by parents linked to that child.
    """
    if current_user["role"] != "parent":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only parents can access this endpoint"
        )

    async with db_pool.acquire() as conn:
        # Verify this child is linked to this parent
        is_linked = await conn.fetchval(
            """
            SELECT EXISTS(
                SELECT 1 FROM parent_links
                WHERE parent_id = $1 AND player_id = $2
            )
            """,
            uuid.UUID(current_user["id"]),
            uuid.UUID(child_id)
        )

        if not is_linked:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This child is not linked to your account"
            )

        row = await conn.fetchrow(
            """
            SELECT
                COUNT(*) as games_played,
                COALESCE(AVG(points)::NUMERIC(10,1), 0) as avg_points,
                COALESCE(AVG(offensive_rebounds + defensive_rebounds)::NUMERIC(10,1), 0) as avg_rebounds,
                COALESCE(AVG(assists)::NUMERIC(10,1), 0) as avg_assists,
                CASE
                    WHEN SUM(field_goals_attempted) > 0
                    THEN (SUM(field_goals_made)::NUMERIC / SUM(field_goals_attempted) * 100)
                    ELSE 0
                END as fg_percentage,
                CASE
                    WHEN SUM(three_pointers_attempted) > 0
                    THEN (SUM(three_pointers_made)::NUMERIC / SUM(three_pointers_attempted) * 100)
                    ELSE 0
                END as three_pt_percentage,
                CASE
                    WHEN SUM(free_throws_attempted) > 0
                    THEN (SUM(free_throws_made)::NUMERIC / SUM(free_throws_attempted) * 100)
                    ELSE 0
                END as ft_percentage
            FROM player_game_stats
            WHERE player_id = $1
            """,
            uuid.UUID(child_id)
        )

    if not row or row["games_played"] == 0:
        # Return zeros if no stats
        return SeasonStatsResponse(
            games_played=0,
            avg_points=0.0,
            avg_rebounds=0.0,
            avg_assists=0.0,
            fg_percentage=0.0,
            three_pt_percentage=0.0,
            ft_percentage=0.0
        )

    return SeasonStatsResponse(
        games_played=row["games_played"],
        avg_points=float(row["avg_points"]),
        avg_rebounds=float(row["avg_rebounds"]),
        avg_assists=float(row["avg_assists"]),
        fg_percentage=float(row["fg_percentage"]),
        three_pt_percentage=float(row["three_pt_percentage"]),
        ft_percentage=float(row["ft_percentage"])
    )
