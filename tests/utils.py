"""
Test utilities and helper functions.

Provides helper functions for creating test data and making authenticated requests.
"""

from typing import Dict, Optional
import uuid
import asyncpg
from httpx import AsyncClient

from backend.auth import hash_password, create_access_token


async def create_test_user(
    db_pool: asyncpg.Pool,
    role: str,
    username: str,
    email: Optional[str] = None,
    display_name: Optional[str] = None
) -> Dict:
    """
    Create a test user in the database.

    Args:
        db_pool: Database connection pool
        role: User role ('coach', 'player', 'parent')
        username: Username
        email: Optional email address
        display_name: Optional display name

    Returns:
        Dictionary with user data including password
    """
    user_id = uuid.uuid4()
    password = f"{username}_password_123"
    password_hash_value = hash_password(password)

    if display_name is None:
        display_name = username.title()

    async with db_pool.acquire() as conn:
        user = await conn.fetchrow(
            """
            INSERT INTO users (id, email, username, password_hash, display_name, role, auth_provider, status)
            VALUES ($1, $2, $3, $4, $5, $6, 'local', 'active')
            RETURNING id, email, username, display_name, role, status, auth_provider, created_at, last_login_at
            """,
            user_id, email, username, password_hash_value, display_name, role
        )

    return {
        "id": str(user["id"]),
        "email": user["email"],
        "username": user["username"],
        "display_name": user["display_name"],
        "role": user["role"],
        "status": user["status"],
        "auth_provider": user["auth_provider"],
        "created_at": user["created_at"],
        "last_login_at": user["last_login_at"],
        "password": password
    }


async def create_test_team(
    db_pool: asyncpg.Pool,
    coach_id: str,
    name: str,
    season: Optional[str] = "2024"
) -> Dict:
    """
    Create a test team with a coach.

    Args:
        db_pool: Database connection pool
        coach_id: UUID of the coach creating the team
        name: Team name
        season: Season (default: "2024")

    Returns:
        Dictionary with team data
    """
    team_id = uuid.uuid4()

    async with db_pool.acquire() as conn:
        team = await conn.fetchrow(
            """
            INSERT INTO teams (id, name, season, created_by)
            VALUES ($1, $2, $3, $4)
            RETURNING id, name, season, created_by, created_at
            """,
            team_id, name, season, uuid.UUID(coach_id)
        )

        # Add coach to team
        await conn.execute(
            """
            INSERT INTO team_coaches (team_id, coach_id, role)
            VALUES ($1, $2, 'head')
            """,
            team_id, uuid.UUID(coach_id)
        )

    return {
        "id": str(team["id"]),
        "name": team["name"],
        "season": team["season"],
        "created_by": str(team["created_by"]),
        "created_at": team["created_at"]
    }


async def add_player_to_team(
    db_pool: asyncpg.Pool,
    team_id: str,
    player_id: str
) -> None:
    """
    Add a player to a team roster.

    Args:
        db_pool: Database connection pool
        team_id: UUID of the team
        player_id: UUID of the player
    """
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO team_players (team_id, player_id)
            VALUES ($1, $2)
            ON CONFLICT DO NOTHING
            """,
            uuid.UUID(team_id), uuid.UUID(player_id)
        )


async def link_parent_to_player(
    db_pool: asyncpg.Pool,
    parent_id: str,
    player_id: str
) -> None:
    """
    Link a parent to a player.

    Args:
        db_pool: Database connection pool
        parent_id: UUID of the parent
        player_id: UUID of the player
    """
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO parent_links (parent_id, player_id, verified_at)
            VALUES ($1, $2, NOW())
            ON CONFLICT DO NOTHING
            """,
            uuid.UUID(parent_id), uuid.UUID(player_id)
        )


async def make_authenticated_request(
    client: AsyncClient,
    method: str,
    url: str,
    user_id: str,
    role: str,
    **kwargs
) -> any:
    """
    Make an authenticated HTTP request.

    Args:
        client: AsyncClient instance
        method: HTTP method ('get', 'post', 'put', 'delete')
        url: Request URL
        user_id: User ID for token
        role: User role for token
        **kwargs: Additional arguments to pass to the request

    Returns:
        Response object
    """
    token = create_access_token(user_id, role)
    headers = kwargs.get("headers", {})
    headers["Authorization"] = f"Bearer {token}"
    kwargs["headers"] = headers

    method_func = getattr(client, method.lower())
    return await method_func(url, **kwargs)


def assert_error_response(response, expected_status: int, expected_detail_contains: Optional[str] = None):
    """
    Assert that a response is an error with expected properties.

    Args:
        response: HTTP response object
        expected_status: Expected HTTP status code
        expected_detail_contains: Optional string that should be in error detail
    """
    assert response.status_code == expected_status, \
        f"Expected status {expected_status}, got {response.status_code}: {response.text}"

    if expected_status >= 400:
        data = response.json()
        assert "detail" in data, "Error response should have 'detail' field"

        if expected_detail_contains:
            assert expected_detail_contains.lower() in data["detail"].lower(), \
                f"Expected '{expected_detail_contains}' in error detail, got: {data['detail']}"


def assert_success_response(response, expected_status: int = 200):
    """
    Assert that a response is successful.

    Args:
        response: HTTP response object
        expected_status: Expected HTTP status code (default: 200)
    """
    assert response.status_code == expected_status, \
        f"Expected status {expected_status}, got {response.status_code}: {response.text}"


async def create_test_clip_with_assignment(
    db_pool: asyncpg.Pool,
    game_id: str,
    video_id: str,
    player_id: str,
    coach_id: str
) -> Dict:
    """
    Create a test clip and assign it to a player.

    Args:
        db_pool: Database connection pool
        game_id: UUID of the game
        video_id: UUID of the video
        player_id: UUID of the player to assign to
        coach_id: UUID of the coach assigning

    Returns:
        Dictionary with clip and assignment data
    """
    clip_id = uuid.uuid4()
    assignment_id = uuid.uuid4()

    async with db_pool.acquire() as conn:
        # Create clip
        clip = await conn.fetchrow(
            """
            INSERT INTO clips (id, game_id, video_id, start_time, end_time, tags, players, notes, status)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'completed')
            RETURNING id, game_id, video_id, start_time, end_time, tags, players, notes, clip_path, status, created_at
            """,
            clip_id, uuid.UUID(game_id), uuid.UUID(video_id),
            "00:10", "00:20", ["test", "clip"], ["Test Player"], "Test clip"
        )

        # Create assignment
        assignment = await conn.fetchrow(
            """
            INSERT INTO clip_assignments (id, clip_id, player_id, assigned_by, message, priority)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id, clip_id, player_id, assigned_by, message, priority, viewed_at, acknowledged_at, created_at
            """,
            assignment_id, clip_id, uuid.UUID(player_id), uuid.UUID(coach_id),
            "Test assignment", "normal"
        )

    return {
        "clip": {
            "id": str(clip["id"]),
            "game_id": str(clip["game_id"]),
            "video_id": str(clip["video_id"]),
            "start_time": clip["start_time"],
            "end_time": clip["end_time"],
            "tags": clip["tags"],
            "players": clip["players"],
            "notes": clip["notes"],
            "clip_path": clip["clip_path"],
            "status": clip["status"],
            "created_at": clip["created_at"]
        },
        "assignment": {
            "id": str(assignment["id"]),
            "clip_id": str(assignment["clip_id"]),
            "player_id": str(assignment["player_id"]),
            "assigned_by": str(assignment["assigned_by"]),
            "message": assignment["message"],
            "priority": assignment["priority"],
            "viewed_at": assignment["viewed_at"],
            "acknowledged_at": assignment["acknowledged_at"],
            "created_at": assignment["created_at"]
        }
    }
