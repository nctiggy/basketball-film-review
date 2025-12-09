"""
FastAPI dependencies for authentication and authorization.

Provides dependency functions that can be used to protect routes and
verify user permissions.
"""

from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import uuid
from jwt.exceptions import InvalidTokenError

from .jwt import decode_token

# Global db_pool will be imported from app.py at runtime
# This allows us to use the database pool in dependencies
db_pool = None


def set_db_pool(pool):
    """Set the global database pool for use in dependencies."""
    global db_pool
    db_pool = pool


# HTTP Bearer token scheme
security = HTTPBearer(auto_error=False)


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[dict]:
    """
    Get the current authenticated user (optional).

    Returns None if no valid token is provided, otherwise returns user dict.

    Args:
        credentials: HTTP Bearer token credentials

    Returns:
        User dictionary or None
    """
    if not credentials:
        return None

    try:
        # Decode the JWT token
        payload = decode_token(credentials.credentials)

        # Verify it's an access token
        if payload.get("type") != "access":
            return None

        # Get user ID from token
        user_id = payload.get("sub")
        if not user_id:
            return None

        # Fetch user from database
        async with db_pool.acquire() as conn:
            user = await conn.fetchrow(
                """
                SELECT id, email, username, display_name, role, phone, status,
                       auth_provider, created_at, last_login_at
                FROM users
                WHERE id = $1 AND status != 'suspended'
                """,
                uuid.UUID(user_id)
            )

            if not user:
                return None

            # Convert to dict and stringify UUID
            return {
                "id": str(user["id"]),
                "email": user["email"],
                "username": user["username"],
                "display_name": user["display_name"],
                "role": user["role"],
                "phone": user["phone"],
                "status": user["status"],
                "auth_provider": user["auth_provider"],
                "created_at": user["created_at"],
                "last_login_at": user["last_login_at"]
            }

    except InvalidTokenError:
        return None
    except Exception:
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Get the current authenticated user (required).

    Raises 401 if no valid token is provided.

    Args:
        credentials: HTTP Bearer token credentials

    Returns:
        User dictionary

    Raises:
        HTTPException: 401 if not authenticated
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        # Decode the JWT token
        payload = decode_token(credentials.credentials)

        # Verify it's an access token
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Get user ID from token
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Fetch user from database
        async with db_pool.acquire() as conn:
            user = await conn.fetchrow(
                """
                SELECT id, email, username, display_name, role, phone, status,
                       auth_provider, created_at, last_login_at
                FROM users
                WHERE id = $1
                """,
                uuid.UUID(user_id)
            )

            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            if user["status"] == "suspended":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Account suspended"
                )

            # Convert to dict and stringify UUID
            return {
                "id": str(user["id"]),
                "email": user["email"],
                "username": user["username"],
                "display_name": user["display_name"],
                "role": user["role"],
                "phone": user["phone"],
                "status": user["status"],
                "auth_provider": user["auth_provider"],
                "created_at": user["created_at"],
                "last_login_at": user["last_login_at"]
            }

    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication error: {str(e)}"
        )


def require_role(required_role: str):
    """
    Create a dependency that requires a specific role.

    Args:
        required_role: The role required ('coach', 'player', 'parent')

    Returns:
        Dependency function that checks the user's role
    """
    async def role_checker(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user["role"] != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {required_role} role"
            )
        return current_user

    return role_checker


def require_coach():
    """
    Shorthand dependency for requiring coach role.

    Returns:
        Dependency function that checks for coach role
    """
    return require_role("coach")


async def require_team_access(team_id: str, user: dict = Depends(get_current_user)) -> bool:
    """
    Verify that a user has access to a team.

    Coaches must be associated with the team.
    Players must be on the team roster.
    Parents must have a child on the team.

    Args:
        team_id: The team UUID to check access for
        user: The current authenticated user

    Returns:
        True if user has access

    Raises:
        HTTPException: 403 if user doesn't have access to the team
    """
    try:
        team_uuid = uuid.UUID(team_id)
        user_uuid = uuid.UUID(user["id"])

        async with db_pool.acquire() as conn:
            if user["role"] == "coach":
                # Check if coach is associated with the team
                coach_access = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM team_coaches WHERE team_id = $1 AND coach_id = $2)",
                    team_uuid, user_uuid
                )
                if not coach_access:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="No access to this team"
                    )

            elif user["role"] == "player":
                # Check if player is on the team roster
                player_access = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM team_players WHERE team_id = $1 AND player_id = $2)",
                    team_uuid, user_uuid
                )
                if not player_access:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="No access to this team"
                    )

            elif user["role"] == "parent":
                # Check if parent has a child on the team
                parent_access = await conn.fetchval(
                    """
                    SELECT EXISTS(
                        SELECT 1 FROM parent_links pl
                        JOIN team_players tp ON pl.player_id = tp.player_id
                        WHERE tp.team_id = $1 AND pl.parent_id = $2
                    )
                    """,
                    team_uuid, user_uuid
                )
                if not parent_access:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="No access to this team"
                    )

        return True

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid team ID"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error checking team access: {str(e)}"
        )
