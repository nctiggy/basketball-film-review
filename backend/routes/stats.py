"""
Player stats routes.

Provides endpoints for managing and viewing player game statistics.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
import uuid

from backend.models.stats import (
    GameStatsRequest,
    PlayerGameStats,
    GameStatsResponse,
    PlayerStatsResponse,
    TeamStatsResponse
)
from backend.auth import get_current_user
from backend.auth.dependencies import db_pool, require_coach

router = APIRouter(tags=["Stats"])


@router.get("/games/{game_id}/stats", response_model=GameStatsResponse)
async def get_game_stats(
    game_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get all player stats for a game.

    Coaches can view all team stats.
    Players can only view their own stats.
    """
    async with db_pool.acquire() as conn:
        game = await conn.fetchrow(
            "SELECT id, name, team_id FROM games WHERE id = $1",
            uuid.UUID(game_id)
        )

        if not game:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Game not found"
            )

        if current_user["role"] == "coach":
            # Verify access to team
            if game["team_id"]:
                has_access = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM team_coaches WHERE team_id = $1 AND coach_id = $2)",
                    game["team_id"], uuid.UUID(current_user["id"])
                )
                if not has_access:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="No access to this team"
                    )

            # Get all stats
            rows = await conn.fetch(
                """
                SELECT pgs.player_id, u.display_name as player_name,
                       pgs.points, pgs.field_goals_made, pgs.field_goals_attempted,
                       pgs.three_pointers_made, pgs.three_pointers_attempted,
                       pgs.free_throws_made, pgs.free_throws_attempted,
                       pgs.offensive_rebounds, pgs.defensive_rebounds,
                       pgs.assists, pgs.steals, pgs.blocks, pgs.turnovers,
                       pgs.fouls, pgs.minutes_played
                FROM player_game_stats pgs
                JOIN users u ON pgs.player_id = u.id
                WHERE pgs.game_id = $1
                ORDER BY u.display_name
                """,
                uuid.UUID(game_id)
            )
        else:
            # Players and parents see their own/children's stats
            player_filter = uuid.UUID(current_user["id"]) if current_user["role"] == "player" else None
            
            if current_user["role"] == "parent":
                # Get stats for linked children
                rows = await conn.fetch(
                    """
                    SELECT pgs.player_id, u.display_name as player_name,
                           pgs.points, pgs.field_goals_made, pgs.field_goals_attempted,
                           pgs.three_pointers_made, pgs.three_pointers_attempted,
                           pgs.free_throws_made, pgs.free_throws_attempted,
                           pgs.offensive_rebounds, pgs.defensive_rebounds,
                           pgs.assists, pgs.steals, pgs.blocks, pgs.turnovers,
                           pgs.fouls, pgs.minutes_played
                    FROM player_game_stats pgs
                    JOIN users u ON pgs.player_id = u.id
                    JOIN parent_links pl ON pgs.player_id = pl.player_id
                    WHERE pgs.game_id = $1 AND pl.parent_id = $2
                    """,
                    uuid.UUID(game_id), uuid.UUID(current_user["id"])
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT pgs.player_id, u.display_name as player_name,
                           pgs.points, pgs.field_goals_made, pgs.field_goals_attempted,
                           pgs.three_pointers_made, pgs.three_pointers_attempted,
                           pgs.free_throws_made, pgs.free_throws_attempted,
                           pgs.offensive_rebounds, pgs.defensive_rebounds,
                           pgs.assists, pgs.steals, pgs.blocks, pgs.turnovers,
                           pgs.fouls, pgs.minutes_played
                    FROM player_game_stats pgs
                    JOIN users u ON pgs.player_id = u.id
                    WHERE pgs.game_id = $1 AND pgs.player_id = $2
                    """,
                    uuid.UUID(game_id), player_filter
                )

    stats = [
        PlayerGameStats(
            player_id=str(row["player_id"]),
            player_name=row["player_name"],
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
            minutes_played=row["minutes_played"]
        )
        for row in rows
    ]

    return GameStatsResponse(
        game_id=str(game["id"]),
        game_name=game["name"],
        stats=stats
    )


@router.post("/games/{game_id}/stats", status_code=status.HTTP_201_CREATED)
async def add_or_update_game_stats(
    game_id: str,
    request: GameStatsRequest,
    current_user: dict = Depends(require_coach())
):
    """
    Add or update player stats for a game.

    Coach must have access to the game's team.
    """
    async with db_pool.acquire() as conn:
        game = await conn.fetchrow(
            "SELECT id, team_id FROM games WHERE id = $1",
            uuid.UUID(game_id)
        )

        if not game:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Game not found"
            )

        if game["team_id"]:
            has_access = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM team_coaches WHERE team_id = $1 AND coach_id = $2)",
                game["team_id"], uuid.UUID(current_user["id"])
            )
            if not has_access:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No access to this team"
                )

        # Insert or update stats for each player
        for stat in request.stats:
            await conn.execute(
                """
                INSERT INTO player_game_stats (
                    game_id, player_id, points, field_goals_made, field_goals_attempted,
                    three_pointers_made, three_pointers_attempted, free_throws_made, free_throws_attempted,
                    offensive_rebounds, defensive_rebounds, assists, steals, blocks,
                    turnovers, fouls, minutes_played, recorded_by
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
                ON CONFLICT (game_id, player_id)
                DO UPDATE SET
                    points = $3, field_goals_made = $4, field_goals_attempted = $5,
                    three_pointers_made = $6, three_pointers_attempted = $7,
                    free_throws_made = $8, free_throws_attempted = $9,
                    offensive_rebounds = $10, defensive_rebounds = $11,
                    assists = $12, steals = $13, blocks = $14,
                    turnovers = $15, fouls = $16, minutes_played = $17,
                    updated_at = NOW()
                """,
                uuid.UUID(game_id), uuid.UUID(stat.player_id),
                stat.points, stat.field_goals_made, stat.field_goals_attempted,
                stat.three_pointers_made, stat.three_pointers_attempted,
                stat.free_throws_made, stat.free_throws_attempted,
                stat.offensive_rebounds, stat.defensive_rebounds,
                stat.assists, stat.steals, stat.blocks,
                stat.turnovers, stat.fouls, stat.minutes_played,
                uuid.UUID(current_user["id"])
            )

    return {"message": f"Stats updated for {len(request.stats)} players"}


@router.get("/players/{player_id}/stats", response_model=PlayerStatsResponse)
async def get_player_stats(
    player_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get aggregate stats for a player across all games.

    Players can only view their own stats.
    Coaches can view stats for players on their teams.
    """
    async with db_pool.acquire() as conn:
        # Authorization check
        if current_user["role"] == "player":
            if current_user["id"] != player_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot view other players' stats"
                )
        elif current_user["role"] == "coach":
            # Verify player is on one of coach's teams
            has_access = await conn.fetchval(
                """
                SELECT EXISTS(
                    SELECT 1 FROM team_players tp
                    JOIN team_coaches tc ON tp.team_id = tc.team_id
                    WHERE tp.player_id = $1 AND tc.coach_id = $2
                )
                """,
                uuid.UUID(player_id), uuid.UUID(current_user["id"])
            )
            if not has_access:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No access to this player"
                )

        # Get aggregate stats
        stats = await conn.fetchrow(
            """
            SELECT 
                u.display_name as player_name,
                COUNT(*) as games_played,
                COALESCE(SUM(points), 0) as total_points,
                COALESCE(SUM(offensive_rebounds + defensive_rebounds), 0) as total_rebounds,
                COALESCE(SUM(assists), 0) as total_assists,
                COALESCE(AVG(points), 0) as avg_points,
                COALESCE(AVG(offensive_rebounds + defensive_rebounds), 0) as avg_rebounds,
                COALESCE(AVG(assists), 0) as avg_assists,
                COALESCE(SUM(field_goals_made), 0) as total_fgm,
                COALESCE(SUM(field_goals_attempted), 0) as total_fga,
                COALESCE(SUM(three_pointers_made), 0) as total_tpm,
                COALESCE(SUM(three_pointers_attempted), 0) as total_tpa,
                COALESCE(SUM(free_throws_made), 0) as total_ftm,
                COALESCE(SUM(free_throws_attempted), 0) as total_fta
            FROM player_game_stats pgs
            JOIN users u ON pgs.player_id = u.id
            WHERE pgs.player_id = $1
            GROUP BY u.display_name
            """,
            uuid.UUID(player_id)
        )

        if not stats:
            # Player exists but has no stats yet
            player_name = await conn.fetchval(
                "SELECT display_name FROM users WHERE id = $1",
                uuid.UUID(player_id)
            )
            if not player_name:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Player not found"
                )
            
            return PlayerStatsResponse(
                player_id=player_id,
                player_name=player_name,
                games_played=0,
                total_points=0,
                total_rebounds=0,
                total_assists=0,
                avg_points=0.0,
                avg_rebounds=0.0,
                avg_assists=0.0,
                fg_percentage=None,
                three_pt_percentage=None,
                ft_percentage=None
            )

    # Calculate percentages
    fg_pct = (stats["total_fgm"] / stats["total_fga"] * 100) if stats["total_fga"] > 0 else None
    three_pct = (stats["total_tpm"] / stats["total_tpa"] * 100) if stats["total_tpa"] > 0 else None
    ft_pct = (stats["total_ftm"] / stats["total_fta"] * 100) if stats["total_fta"] > 0 else None

    return PlayerStatsResponse(
        player_id=player_id,
        player_name=stats["player_name"],
        games_played=stats["games_played"],
        total_points=stats["total_points"],
        total_rebounds=stats["total_rebounds"],
        total_assists=stats["total_assists"],
        avg_points=round(float(stats["avg_points"]), 1),
        avg_rebounds=round(float(stats["avg_rebounds"]), 1),
        avg_assists=round(float(stats["avg_assists"]), 1),
        fg_percentage=round(fg_pct, 1) if fg_pct is not None else None,
        three_pt_percentage=round(three_pct, 1) if three_pct is not None else None,
        ft_percentage=round(ft_pct, 1) if ft_pct is not None else None
    )


@router.get("/teams/{team_id}/stats", response_model=TeamStatsResponse)
async def get_team_stats(
    team_id: str,
    current_user: dict = Depends(require_coach())
):
    """
    Get aggregate stats for all players on a team.

    Coach must have access to the team.
    """
    async with db_pool.acquire() as conn:
        # Verify access
        has_access = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM team_coaches WHERE team_id = $1 AND coach_id = $2)",
            uuid.UUID(team_id), uuid.UUID(current_user["id"])
        )

        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No access to this team"
            )

        team = await conn.fetchrow(
            "SELECT id, name FROM teams WHERE id = $1",
            uuid.UUID(team_id)
        )

        if not team:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Team not found"
            )

        # Get player IDs on team
        player_ids = await conn.fetch(
            "SELECT player_id FROM team_players WHERE team_id = $1",
            uuid.UUID(team_id)
        )

    # Get stats for each player
    player_stats = []
    for player_row in player_ids:
        # Reuse get_player_stats logic
        async with db_pool.acquire() as conn:
            stats = await conn.fetchrow(
                """
                SELECT 
                    u.display_name as player_name,
                    COUNT(*) as games_played,
                    COALESCE(SUM(points), 0) as total_points,
                    COALESCE(SUM(offensive_rebounds + defensive_rebounds), 0) as total_rebounds,
                    COALESCE(SUM(assists), 0) as total_assists,
                    COALESCE(AVG(points), 0) as avg_points,
                    COALESCE(AVG(offensive_rebounds + defensive_rebounds), 0) as avg_rebounds,
                    COALESCE(AVG(assists), 0) as avg_assists,
                    COALESCE(SUM(field_goals_made), 0) as total_fgm,
                    COALESCE(SUM(field_goals_attempted), 0) as total_fga,
                    COALESCE(SUM(three_pointers_made), 0) as total_tpm,
                    COALESCE(SUM(three_pointers_attempted), 0) as total_tpa,
                    COALESCE(SUM(free_throws_made), 0) as total_ftm,
                    COALESCE(SUM(free_throws_attempted), 0) as total_fta
                FROM player_game_stats pgs
                JOIN users u ON pgs.player_id = u.id
                WHERE pgs.player_id = $1
                GROUP BY u.display_name
                """,
                player_row["player_id"]
            )

            if stats:
                fg_pct = (stats["total_fgm"] / stats["total_fga"] * 100) if stats["total_fga"] > 0 else None
                three_pct = (stats["total_tpm"] / stats["total_tpa"] * 100) if stats["total_tpa"] > 0 else None
                ft_pct = (stats["total_ftm"] / stats["total_fta"] * 100) if stats["total_fta"] > 0 else None

                player_stats.append(
                    PlayerStatsResponse(
                        player_id=str(player_row["player_id"]),
                        player_name=stats["player_name"],
                        games_played=stats["games_played"],
                        total_points=stats["total_points"],
                        total_rebounds=stats["total_rebounds"],
                        total_assists=stats["total_assists"],
                        avg_points=round(float(stats["avg_points"]), 1),
                        avg_rebounds=round(float(stats["avg_rebounds"]), 1),
                        avg_assists=round(float(stats["avg_assists"]), 1),
                        fg_percentage=round(fg_pct, 1) if fg_pct is not None else None,
                        three_pt_percentage=round(three_pct, 1) if three_pct is not None else None,
                        ft_percentage=round(ft_pct, 1) if ft_pct is not None else None
                    )
                )

    # Count total games for team
    async with db_pool.acquire() as conn:
        total_games = await conn.fetchval(
            "SELECT COUNT(*) FROM games WHERE team_id = $1",
            uuid.UUID(team_id)
        )

    return TeamStatsResponse(
        team_id=str(team["id"]),
        team_name=team["name"],
        total_games=total_games or 0,
        player_stats=player_stats
    )
