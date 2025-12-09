"""
Teams routes.

Provides endpoints for team management, coaches, and roster.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
import uuid
from datetime import datetime

from backend.models.team import (
    TeamCreate,
    TeamUpdate,
    TeamResponse,
    CoachResponse,
    AddCoachRequest,
    RosterPlayerResponse,
    AddPlayerRequest
)
from backend.auth import get_current_user
from backend.auth.dependencies import db_pool, require_coach

router = APIRouter(prefix="/teams", tags=["Teams"])


@router.get("", response_model=List[TeamResponse])
async def list_teams(current_user: dict = Depends(require_coach())):
    """
    List all teams the coach is associated with.

    Only accessible by coaches.
    """
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT t.id, t.name, t.season, t.created_by, t.created_at
            FROM teams t
            JOIN team_coaches tc ON t.id = tc.team_id
            WHERE tc.coach_id = $1
            ORDER BY t.created_at DESC
            """,
            uuid.UUID(current_user["id"])
        )

    return [
        TeamResponse(
            id=str(row["id"]),
            name=row["name"],
            season=row["season"],
            created_by=str(row["created_by"]) if row["created_by"] else None,
            created_at=row["created_at"]
        )
        for row in rows
    ]


@router.post("", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
async def create_team(
    team: TeamCreate,
    current_user: dict = Depends(require_coach())
):
    """
    Create a new team.

    The creating coach is automatically added as the head coach.
    """
    async with db_pool.acquire() as conn:
        team_id = uuid.uuid4()

        # Create team
        row = await conn.fetchrow(
            """
            INSERT INTO teams (id, name, season, created_by)
            VALUES ($1, $2, $3, $4)
            RETURNING id, name, season, created_by, created_at
            """,
            team_id, team.name, team.season, uuid.UUID(current_user["id"])
        )

        # Add creator as head coach
        await conn.execute(
            """
            INSERT INTO team_coaches (team_id, coach_id, role)
            VALUES ($1, $2, 'head')
            """,
            team_id, uuid.UUID(current_user["id"])
        )

    return TeamResponse(
        id=str(row["id"]),
        name=row["name"],
        season=row["season"],
        created_by=str(row["created_by"]),
        created_at=row["created_at"]
    )


@router.get("/{team_id}", response_model=TeamResponse)
async def get_team(
    team_id: str,
    current_user: dict = Depends(require_coach())
):
    """
    Get details for a specific team.

    Coach must be associated with the team.
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

        row = await conn.fetchrow(
            "SELECT id, name, season, created_by, created_at FROM teams WHERE id = $1",
            uuid.UUID(team_id)
        )

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Team not found"
            )

    return TeamResponse(
        id=str(row["id"]),
        name=row["name"],
        season=row["season"],
        created_by=str(row["created_by"]) if row["created_by"] else None,
        created_at=row["created_at"]
    )


@router.put("/{team_id}", response_model=TeamResponse)
async def update_team(
    team_id: str,
    update: TeamUpdate,
    current_user: dict = Depends(require_coach())
):
    """
    Update team details.

    Coach must be associated with the team.
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

        # Build dynamic update query
        update_fields = []
        params = []
        param_count = 1

        if update.name is not None:
            update_fields.append(f"name = ${param_count}")
            params.append(update.name)
            param_count += 1

        if update.season is not None:
            update_fields.append(f"season = ${param_count}")
            params.append(update.season)
            param_count += 1

        if not update_fields:
            # No fields to update, fetch and return current data
            row = await conn.fetchrow(
                "SELECT id, name, season, created_by, created_at FROM teams WHERE id = $1",
                uuid.UUID(team_id)
            )
        else:
            params.append(uuid.UUID(team_id))
            query = f"""
                UPDATE teams
                SET {', '.join(update_fields)}
                WHERE id = ${param_count}
                RETURNING id, name, season, created_by, created_at
            """
            row = await conn.fetchrow(query, *params)

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Team not found"
            )

    return TeamResponse(
        id=str(row["id"]),
        name=row["name"],
        season=row["season"],
        created_by=str(row["created_by"]) if row["created_by"] else None,
        created_at=row["created_at"]
    )


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team(
    team_id: str,
    current_user: dict = Depends(require_coach())
):
    """
    Delete a team.

    Only the team creator can delete the team.
    Cascades to all related data.
    """
    async with db_pool.acquire() as conn:
        # Verify user is the creator
        team = await conn.fetchrow(
            "SELECT created_by FROM teams WHERE id = $1",
            uuid.UUID(team_id)
        )

        if not team:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Team not found"
            )

        if str(team["created_by"]) != current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the team creator can delete the team"
            )

        await conn.execute("DELETE FROM teams WHERE id = $1", uuid.UUID(team_id))


# Coach management endpoints

@router.get("/{team_id}/coaches", response_model=List[CoachResponse])
async def list_team_coaches(
    team_id: str,
    current_user: dict = Depends(require_coach())
):
    """
    List all coaches for a team.

    Coach must be associated with the team.
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

        rows = await conn.fetch(
            """
            SELECT u.id, u.display_name, u.email, tc.role, tc.added_at
            FROM team_coaches tc
            JOIN users u ON tc.coach_id = u.id
            WHERE tc.team_id = $1
            ORDER BY tc.added_at ASC
            """,
            uuid.UUID(team_id)
        )

    return [
        CoachResponse(
            id=str(row["id"]),
            display_name=row["display_name"],
            email=row["email"],
            role=row["role"],
            added_at=row["added_at"]
        )
        for row in rows
    ]


@router.post("/{team_id}/coaches", response_model=CoachResponse, status_code=status.HTTP_201_CREATED)
async def add_coach_to_team(
    team_id: str,
    request: AddCoachRequest,
    current_user: dict = Depends(require_coach())
):
    """
    Add a coach to a team.

    Requires head coach role on the team.
    """
    async with db_pool.acquire() as conn:
        # Verify user is head coach
        user_role = await conn.fetchval(
            "SELECT role FROM team_coaches WHERE team_id = $1 AND coach_id = $2",
            uuid.UUID(team_id), uuid.UUID(current_user["id"])
        )

        if user_role != "head":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only head coaches can add other coaches"
            )

        # Verify target user is a coach
        coach = await conn.fetchrow(
            "SELECT id, display_name, email FROM users WHERE id = $1 AND role = 'coach'",
            uuid.UUID(request.coach_id)
        )

        if not coach:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Coach not found"
            )

        # Check if already on team
        existing = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM team_coaches WHERE team_id = $1 AND coach_id = $2)",
            uuid.UUID(team_id), uuid.UUID(request.coach_id)
        )

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Coach already on team"
            )

        # Add coach
        row = await conn.fetchrow(
            """
            INSERT INTO team_coaches (team_id, coach_id, role)
            VALUES ($1, $2, $3)
            RETURNING added_at
            """,
            uuid.UUID(team_id), uuid.UUID(request.coach_id), request.role
        )

    return CoachResponse(
        id=str(coach["id"]),
        display_name=coach["display_name"],
        email=coach["email"],
        role=request.role,
        added_at=row["added_at"]
    )


@router.delete("/{team_id}/coaches/{coach_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_coach_from_team(
    team_id: str,
    coach_id: str,
    current_user: dict = Depends(require_coach())
):
    """
    Remove a coach from a team.

    Requires head coach role. Cannot remove the last coach.
    """
    async with db_pool.acquire() as conn:
        # Verify user is head coach
        user_role = await conn.fetchval(
            "SELECT role FROM team_coaches WHERE team_id = $1 AND coach_id = $2",
            uuid.UUID(team_id), uuid.UUID(current_user["id"])
        )

        if user_role != "head":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only head coaches can remove coaches"
            )

        # Check if removing last coach
        coach_count = await conn.fetchval(
            "SELECT COUNT(*) FROM team_coaches WHERE team_id = $1",
            uuid.UUID(team_id)
        )

        if coach_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove the last coach from a team"
            )

        result = await conn.execute(
            "DELETE FROM team_coaches WHERE team_id = $1 AND coach_id = $2",
            uuid.UUID(team_id), uuid.UUID(coach_id)
        )

        if result == "DELETE 0":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Coach not found on team"
            )


# Roster management endpoints

@router.get("/{team_id}/players", response_model=List[RosterPlayerResponse])
async def list_team_players(
    team_id: str,
    current_user: dict = Depends(require_coach())
):
    """
    List all players on the team roster.

    Coach must be associated with the team.
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

        rows = await conn.fetch(
            """
            SELECT u.id, u.display_name, u.username, u.status,
                   pp.jersey_number, pp.position, pp.graduation_year,
                   tp.added_at
            FROM team_players tp
            JOIN users u ON tp.player_id = u.id
            LEFT JOIN player_profiles pp ON u.id = pp.user_id
            WHERE tp.team_id = $1
            ORDER BY u.display_name ASC
            """,
            uuid.UUID(team_id)
        )

    return [
        RosterPlayerResponse(
            id=str(row["id"]),
            display_name=row["display_name"],
            username=row["username"],
            jersey_number=row["jersey_number"],
            position=row["position"],
            graduation_year=row["graduation_year"],
            status=row["status"],
            added_at=row["added_at"]
        )
        for row in rows
    ]


@router.post("/{team_id}/players", response_model=dict, status_code=status.HTTP_201_CREATED)
async def add_player_to_team(
    team_id: str,
    request: AddPlayerRequest,
    current_user: dict = Depends(require_coach())
):
    """
    Add a player to the team.

    This creates a user account with status 'invited' and generates an invite code.
    The player claims the invite to set their credentials.
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

        # Create user with invited status
        user_id = uuid.uuid4()
        user = await conn.fetchrow(
            """
            INSERT INTO users (id, display_name, role, status, created_by)
            VALUES ($1, $2, 'player', 'invited', $3)
            RETURNING id, display_name, status, created_at
            """,
            user_id, request.display_name, uuid.UUID(current_user["id"])
        )

        # Create player profile if extra info provided
        if request.jersey_number or request.position or request.graduation_year:
            await conn.execute(
                """
                INSERT INTO player_profiles (user_id, jersey_number, position, graduation_year)
                VALUES ($1, $2, $3, $4)
                """,
                user_id, request.jersey_number, request.position, request.graduation_year
            )

        # Add to team
        added = await conn.fetchrow(
            """
            INSERT INTO team_players (team_id, player_id)
            VALUES ($1, $2)
            RETURNING added_at
            """,
            uuid.UUID(team_id), user_id
        )

        # Generate invite code
        import secrets
        invite_code = secrets.token_urlsafe(16)

        invite = await conn.fetchrow(
            """
            INSERT INTO invites (code, team_id, target_role, target_name, expires_at, created_by)
            VALUES ($1, $2, 'player', $3, NOW() + INTERVAL '30 days', $4)
            RETURNING id, code, expires_at
            """,
            invite_code, uuid.UUID(team_id), request.display_name, uuid.UUID(current_user["id"])
        )

    return {
        "player": {
            "id": str(user["id"]),
            "display_name": user["display_name"],
            "status": user["status"],
            "added_at": added["added_at"]
        },
        "invite": {
            "id": str(invite["id"]),
            "code": invite["code"],
            "expires_at": invite["expires_at"].isoformat()
        }
    }


@router.delete("/{team_id}/players/{player_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_player_from_team(
    team_id: str,
    player_id: str,
    current_user: dict = Depends(require_coach())
):
    """
    Remove a player from the team roster.

    Coach must be associated with the team.
    This does NOT delete the user account.
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

        result = await conn.execute(
            "DELETE FROM team_players WHERE team_id = $1 AND player_id = $2",
            uuid.UUID(team_id), uuid.UUID(player_id)
        )

        if result == "DELETE 0":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Player not found on team"
            )
