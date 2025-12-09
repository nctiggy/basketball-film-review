"""
Invites routes.

Provides endpoints for managing and claiming invite codes.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
import uuid
import secrets
from datetime import datetime, timedelta

from backend.models.invite import (
    InviteCreate,
    InviteResponse,
    InvitePreview
)
from backend.auth import get_current_user
from backend.auth.dependencies import db_pool, require_coach

router = APIRouter(prefix="/invites", tags=["Invites"])


@router.get("", response_model=List[InviteResponse])
async def list_invites(current_user: dict = Depends(require_coach())):
    """
    List all invites created by the current coach.

    Shows both claimed and unclaimed invites.
    """
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, code, team_id, target_role, target_name,
                   linked_player_id, expires_at, claimed_by, claimed_at,
                   created_by, created_at
            FROM invites
            WHERE created_by = $1
            ORDER BY created_at DESC
            """,
            uuid.UUID(current_user["id"])
        )

    return [
        InviteResponse(
            id=str(row["id"]),
            code=row["code"],
            team_id=str(row["team_id"]),
            target_role=row["target_role"],
            target_name=row["target_name"],
            linked_player_id=str(row["linked_player_id"]) if row["linked_player_id"] else None,
            expires_at=row["expires_at"],
            claimed_by=str(row["claimed_by"]) if row["claimed_by"] else None,
            claimed_at=row["claimed_at"],
            created_by=str(row["created_by"]) if row["created_by"] else None,
            created_at=row["created_at"]
        )
        for row in rows
    ]


@router.post("", response_model=InviteResponse, status_code=status.HTTP_201_CREATED)
async def create_invite(
    invite: InviteCreate,
    current_user: dict = Depends(require_coach())
):
    """
    Create a new invite code.

    For player invites, target_name is optional.
    For parent invites, linked_player_id must be provided.
    """
    async with db_pool.acquire() as conn:
        # Verify coach has access to team
        has_access = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM team_coaches WHERE team_id = $1 AND coach_id = $2)",
            uuid.UUID(invite.team_id), uuid.UUID(current_user["id"])
        )

        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No access to this team"
            )

        # Validate parent invite requirements
        if invite.target_role == "parent":
            if not invite.linked_player_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="linked_player_id is required for parent invites"
                )

            # Verify player exists and is on the team
            player_on_team = await conn.fetchval(
                """
                SELECT EXISTS(
                    SELECT 1 FROM team_players
                    WHERE team_id = $1 AND player_id = $2
                )
                """,
                uuid.UUID(invite.team_id), uuid.UUID(invite.linked_player_id)
            )

            if not player_on_team:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Player not found on this team"
                )

        # Generate unique invite code
        code = secrets.token_urlsafe(16)
        expires_at = datetime.utcnow() + timedelta(days=invite.expires_in_days)

        row = await conn.fetchrow(
            """
            INSERT INTO invites (code, team_id, target_role, target_name,
                               linked_player_id, expires_at, created_by)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id, code, team_id, target_role, target_name,
                      linked_player_id, expires_at, claimed_by, claimed_at,
                      created_by, created_at
            """,
            code,
            uuid.UUID(invite.team_id),
            invite.target_role,
            invite.target_name,
            uuid.UUID(invite.linked_player_id) if invite.linked_player_id else None,
            expires_at,
            uuid.UUID(current_user["id"])
        )

    return InviteResponse(
        id=str(row["id"]),
        code=row["code"],
        team_id=str(row["team_id"]),
        target_role=row["target_role"],
        target_name=row["target_name"],
        linked_player_id=str(row["linked_player_id"]) if row["linked_player_id"] else None,
        expires_at=row["expires_at"],
        claimed_by=str(row["claimed_by"]) if row["claimed_by"] else None,
        claimed_at=row["claimed_at"],
        created_by=str(row["created_by"]),
        created_at=row["created_at"]
    )


@router.get("/{code}", response_model=InvitePreview)
async def preview_invite(code: str):
    """
    Preview an invite code (public endpoint).

    Used to show invite details before account creation.
    No authentication required.
    """
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT i.code, t.name as team_name, i.target_role, i.target_name,
                   i.expires_at, i.claimed_by, i.linked_player_id,
                   u.display_name as linked_player_name
            FROM invites i
            JOIN teams t ON i.team_id = t.id
            LEFT JOIN users u ON i.linked_player_id = u.id
            WHERE i.code = $1
            """,
            code
        )

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invite not found"
            )

        is_valid = (
            row["claimed_by"] is None and
            row["expires_at"] > datetime.utcnow()
        )

    return InvitePreview(
        code=row["code"],
        team_name=row["team_name"],
        target_role=row["target_role"],
        target_name=row["target_name"],
        expires_at=row["expires_at"],
        is_valid=is_valid,
        linked_player_name=row["linked_player_name"]
    )


@router.delete("/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_invite(
    invite_id: str,
    current_user: dict = Depends(require_coach())
):
    """
    Revoke (delete) an invite code.

    Only the creator can revoke an invite.
    """
    async with db_pool.acquire() as conn:
        # Verify ownership
        invite = await conn.fetchrow(
            "SELECT created_by FROM invites WHERE id = $1",
            uuid.UUID(invite_id)
        )

        if not invite:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invite not found"
            )

        if str(invite["created_by"]) != current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the invite creator can revoke it"
            )

        await conn.execute("DELETE FROM invites WHERE id = $1", uuid.UUID(invite_id))
