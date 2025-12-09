"""
Clip assignment routes.

Provides endpoints for assigning clips to players.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
import uuid

from backend.models.assignment import (
    ClipAssignRequest,
    ClipAssignmentResponse
)
from backend.auth import get_current_user
from backend.auth.dependencies import db_pool, require_coach

router = APIRouter(prefix="/clips", tags=["Clip Assignments"])


@router.post("/{clip_id}/assign", response_model=List[ClipAssignmentResponse], status_code=status.HTTP_201_CREATED)
async def assign_clip(
    clip_id: str,
    request: ClipAssignRequest,
    current_user: dict = Depends(require_coach())
):
    """
    Assign a clip to one or more players.

    Coach must have access to the clip's team.
    Players must be on the team roster.
    """
    async with db_pool.acquire() as conn:
        # Get clip and verify it belongs to a game with a team
        clip = await conn.fetchrow(
            """
            SELECT c.id, c.game_id, g.team_id
            FROM clips c
            JOIN games g ON c.game_id = g.id
            WHERE c.id = $1
            """,
            uuid.UUID(clip_id)
        )

        if not clip:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Clip not found"
            )

        if not clip["team_id"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Clip must belong to a game with a team"
            )

        # Verify coach has access to team
        has_access = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM team_coaches WHERE team_id = $1 AND coach_id = $2)",
            clip["team_id"], uuid.UUID(current_user["id"])
        )

        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No access to this team"
            )

        # Verify all players are on the team
        for player_id in request.player_ids:
            player_on_team = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM team_players WHERE team_id = $1 AND player_id = $2)",
                clip["team_id"], uuid.UUID(player_id)
            )

            if not player_on_team:
                player_name = await conn.fetchval(
                    "SELECT display_name FROM users WHERE id = $1",
                    uuid.UUID(player_id)
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Player {player_name or player_id} is not on this team"
                )

        # Create assignments
        assignments = []
        for player_id in request.player_ids:
            # Use INSERT ... ON CONFLICT to handle duplicates
            row = await conn.fetchrow(
                """
                INSERT INTO clip_assignments (clip_id, player_id, assigned_by, message, priority)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (clip_id, player_id)
                DO UPDATE SET message = $4, priority = $5, created_at = NOW()
                RETURNING id, clip_id, player_id, assigned_by, message, priority,
                          viewed_at, acknowledged_at, created_at
                """,
                uuid.UUID(clip_id),
                uuid.UUID(player_id),
                uuid.UUID(current_user["id"]),
                request.message,
                request.priority
            )

            # Get player name
            player_name = await conn.fetchval(
                "SELECT display_name FROM users WHERE id = $1",
                uuid.UUID(player_id)
            )

            assignments.append(
                ClipAssignmentResponse(
                    id=str(row["id"]),
                    clip_id=str(row["clip_id"]),
                    player_id=str(row["player_id"]),
                    player_name=player_name,
                    assigned_by=str(row["assigned_by"]) if row["assigned_by"] else None,
                    message=row["message"],
                    priority=row["priority"],
                    viewed_at=row["viewed_at"],
                    acknowledged_at=row["acknowledged_at"],
                    created_at=row["created_at"]
                )
            )

    return assignments


@router.get("/{clip_id}/assignments", response_model=List[ClipAssignmentResponse])
async def list_clip_assignments(
    clip_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    List all assignments for a clip.

    Coaches can see all assignments for their team's clips.
    Players can only see their own assignment.
    """
    async with db_pool.acquire() as conn:
        # Get clip and team
        clip = await conn.fetchrow(
            """
            SELECT c.id, c.game_id, g.team_id
            FROM clips c
            JOIN games g ON c.game_id = g.id
            WHERE c.id = $1
            """,
            uuid.UUID(clip_id)
        )

        if not clip:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Clip not found"
            )

        if current_user["role"] == "coach":
            # Verify coach has access to team
            has_access = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM team_coaches WHERE team_id = $1 AND coach_id = $2)",
                clip["team_id"], uuid.UUID(current_user["id"])
            )

            if not has_access:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No access to this team"
                )

            # Return all assignments
            rows = await conn.fetch(
                """
                SELECT ca.id, ca.clip_id, ca.player_id, u.display_name as player_name,
                       ca.assigned_by, ca.message, ca.priority, ca.viewed_at,
                       ca.acknowledged_at, ca.created_at
                FROM clip_assignments ca
                JOIN users u ON ca.player_id = u.id
                WHERE ca.clip_id = $1
                ORDER BY ca.created_at DESC
                """,
                uuid.UUID(clip_id)
            )

        elif current_user["role"] == "player":
            # Return only player's own assignment
            rows = await conn.fetch(
                """
                SELECT ca.id, ca.clip_id, ca.player_id, u.display_name as player_name,
                       ca.assigned_by, ca.message, ca.priority, ca.viewed_at,
                       ca.acknowledged_at, ca.created_at
                FROM clip_assignments ca
                JOIN users u ON ca.player_id = u.id
                WHERE ca.clip_id = $1 AND ca.player_id = $2
                """,
                uuid.UUID(clip_id), uuid.UUID(current_user["id"])
            )

        else:
            # Parents can see assignments for their children
            rows = await conn.fetch(
                """
                SELECT ca.id, ca.clip_id, ca.player_id, u.display_name as player_name,
                       ca.assigned_by, ca.message, ca.priority, ca.viewed_at,
                       ca.acknowledged_at, ca.created_at
                FROM clip_assignments ca
                JOIN users u ON ca.player_id = u.id
                JOIN parent_links pl ON ca.player_id = pl.player_id
                WHERE ca.clip_id = $1 AND pl.parent_id = $2
                """,
                uuid.UUID(clip_id), uuid.UUID(current_user["id"])
            )

    return [
        ClipAssignmentResponse(
            id=str(row["id"]),
            clip_id=str(row["clip_id"]),
            player_id=str(row["player_id"]),
            player_name=row["player_name"],
            assigned_by=str(row["assigned_by"]) if row["assigned_by"] else None,
            message=row["message"],
            priority=row["priority"],
            viewed_at=row["viewed_at"],
            acknowledged_at=row["acknowledged_at"],
            created_at=row["created_at"]
        )
        for row in rows
    ]


@router.delete("/{clip_id}/assignments/{player_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_clip_assignment(
    clip_id: str,
    player_id: str,
    current_user: dict = Depends(require_coach())
):
    """
    Remove a clip assignment for a specific player.

    Coach must have access to the clip's team.
    """
    async with db_pool.acquire() as conn:
        # Get clip and verify access
        clip = await conn.fetchrow(
            """
            SELECT c.id, c.game_id, g.team_id
            FROM clips c
            JOIN games g ON c.game_id = g.id
            WHERE c.id = $1
            """,
            uuid.UUID(clip_id)
        )

        if not clip:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Clip not found"
            )

        has_access = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM team_coaches WHERE team_id = $1 AND coach_id = $2)",
            clip["team_id"], uuid.UUID(current_user["id"])
        )

        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No access to this team"
            )

        result = await conn.execute(
            "DELETE FROM clip_assignments WHERE clip_id = $1 AND player_id = $2",
            uuid.UUID(clip_id), uuid.UUID(player_id)
        )

        if result == "DELETE 0":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assignment not found"
            )
