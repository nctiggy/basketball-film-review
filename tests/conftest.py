"""
Pytest configuration and fixtures for testing.

Provides fixtures for:
- Test database setup/teardown
- Authenticated test clients (coach, player, parent)
- Test data creation (teams, clips, assignments)
"""

import os
import uuid
import asyncio
from typing import AsyncGenerator, Dict
import pytest
import asyncpg
from httpx import AsyncClient
from datetime import datetime, timedelta

# Set test environment variables before importing app
os.environ["DATABASE_URL"] = os.getenv("TEST_DATABASE_URL", "postgresql://filmreview:filmreview@localhost:5432/filmreview_test")
os.environ["JWT_SECRET"] = "test-secret-key-do-not-use-in-production"
os.environ["MINIO_ENDPOINT"] = "localhost:9000"
os.environ["MINIO_ACCESS_KEY"] = "minioadmin"
os.environ["MINIO_SECRET_KEY"] = "minioadmin"

from backend.app import app
from backend.auth import create_access_token, hash_password
from backend.auth.dependencies import db_pool as app_db_pool


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def db_pool():
    """Create a database connection pool for testing."""
    pool = await asyncpg.create_pool(os.environ["DATABASE_URL"])
    yield pool
    await pool.close()


@pytest.fixture(scope="function", autouse=True)
async def setup_database(db_pool):
    """Setup and teardown test database before/after each test."""
    # Clean up all tables before each test
    async with db_pool.acquire() as conn:
        # Delete in correct order to respect foreign keys
        await conn.execute("DELETE FROM notifications")
        await conn.execute("DELETE FROM notification_preferences")
        await conn.execute("DELETE FROM player_game_stats")
        await conn.execute("DELETE FROM clip_analyses")
        await conn.execute("DELETE FROM clip_annotations")
        await conn.execute("DELETE FROM clip_assignments")
        await conn.execute("DELETE FROM clips")
        await conn.execute("DELETE FROM videos")
        await conn.execute("DELETE FROM games")
        await conn.execute("DELETE FROM invites")
        await conn.execute("DELETE FROM parent_links")
        await conn.execute("DELETE FROM player_profiles")
        await conn.execute("DELETE FROM team_players")
        await conn.execute("DELETE FROM team_coaches")
        await conn.execute("DELETE FROM teams")
        await conn.execute("DELETE FROM refresh_tokens")
        await conn.execute("DELETE FROM users")

    yield

    # Clean up after test
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM notifications")
        await conn.execute("DELETE FROM notification_preferences")
        await conn.execute("DELETE FROM player_game_stats")
        await conn.execute("DELETE FROM clip_analyses")
        await conn.execute("DELETE FROM clip_annotations")
        await conn.execute("DELETE FROM clip_assignments")
        await conn.execute("DELETE FROM clips")
        await conn.execute("DELETE FROM videos")
        await conn.execute("DELETE FROM games")
        await conn.execute("DELETE FROM invites")
        await conn.execute("DELETE FROM parent_links")
        await conn.execute("DELETE FROM player_profiles")
        await conn.execute("DELETE FROM team_players")
        await conn.execute("DELETE FROM team_coaches")
        await conn.execute("DELETE FROM teams")
        await conn.execute("DELETE FROM refresh_tokens")
        await conn.execute("DELETE FROM users")


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Create an async HTTP client for testing."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
async def test_coach(db_pool) -> Dict:
    """Create a test coach user."""
    user_id = uuid.uuid4()
    password = "testpassword123"
    password_hash = hash_password(password)

    async with db_pool.acquire() as conn:
        user = await conn.fetchrow(
            """
            INSERT INTO users (id, email, username, password_hash, display_name, role, auth_provider, status)
            VALUES ($1, $2, $3, $4, $5, 'coach', 'local', 'active')
            RETURNING id, email, username, display_name, role, status, auth_provider, created_at, last_login_at
            """,
            user_id, "coach@example.com", "coach1", password_hash, "Test Coach"
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
        "password": password  # For testing login
    }


@pytest.fixture
async def test_player(db_pool) -> Dict:
    """Create a test player user."""
    user_id = uuid.uuid4()
    password = "playerpass123"
    password_hash = hash_password(password)

    async with db_pool.acquire() as conn:
        user = await conn.fetchrow(
            """
            INSERT INTO users (id, email, username, password_hash, display_name, role, auth_provider, status)
            VALUES ($1, $2, $3, $4, $5, 'player', 'local', 'active')
            RETURNING id, email, username, display_name, role, status, auth_provider, created_at, last_login_at
            """,
            user_id, "player@example.com", "player1", password_hash, "Test Player"
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


@pytest.fixture
async def test_player_2(db_pool) -> Dict:
    """Create a second test player user for access control testing."""
    user_id = uuid.uuid4()
    password = "playerpass456"
    password_hash = hash_password(password)

    async with db_pool.acquire() as conn:
        user = await conn.fetchrow(
            """
            INSERT INTO users (id, email, username, password_hash, display_name, role, auth_provider, status)
            VALUES ($1, $2, $3, $4, $5, 'player', 'local', 'active')
            RETURNING id, email, username, display_name, role, status, auth_provider, created_at, last_login_at
            """,
            user_id, "player2@example.com", "player2", password_hash, "Test Player 2"
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


@pytest.fixture
async def test_parent(db_pool) -> Dict:
    """Create a test parent user."""
    user_id = uuid.uuid4()
    password = "parentpass123"
    password_hash = hash_password(password)

    async with db_pool.acquire() as conn:
        user = await conn.fetchrow(
            """
            INSERT INTO users (id, email, username, password_hash, display_name, role, auth_provider, status)
            VALUES ($1, $2, $3, $4, $5, 'parent', 'local', 'active')
            RETURNING id, email, username, display_name, role, status, auth_provider, created_at, last_login_at
            """,
            user_id, "parent@example.com", "parent1", password_hash, "Test Parent"
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


@pytest.fixture
async def coach_token(test_coach) -> str:
    """Create a JWT token for the test coach."""
    return create_access_token(test_coach["id"], test_coach["role"])


@pytest.fixture
async def player_token(test_player) -> str:
    """Create a JWT token for the test player."""
    return create_access_token(test_player["id"], test_player["role"])


@pytest.fixture
async def player_2_token(test_player_2) -> str:
    """Create a JWT token for the second test player."""
    return create_access_token(test_player_2["id"], test_player_2["role"])


@pytest.fixture
async def parent_token(test_parent) -> str:
    """Create a JWT token for the test parent."""
    return create_access_token(test_parent["id"], test_parent["role"])


@pytest.fixture
async def test_team(db_pool, test_coach) -> Dict:
    """Create a test team with the coach as head coach."""
    team_id = uuid.uuid4()

    async with db_pool.acquire() as conn:
        team = await conn.fetchrow(
            """
            INSERT INTO teams (id, name, season, created_by)
            VALUES ($1, $2, $3, $4)
            RETURNING id, name, season, created_by, created_at
            """,
            team_id, "Test Team", "2024", uuid.UUID(test_coach["id"])
        )

        # Add coach to team
        await conn.execute(
            """
            INSERT INTO team_coaches (team_id, coach_id, role)
            VALUES ($1, $2, 'head')
            """,
            team_id, uuid.UUID(test_coach["id"])
        )

    return {
        "id": str(team["id"]),
        "name": team["name"],
        "season": team["season"],
        "created_by": str(team["created_by"]),
        "created_at": team["created_at"]
    }


@pytest.fixture
async def test_game(db_pool, test_team) -> Dict:
    """Create a test game linked to the test team."""
    game_id = uuid.uuid4()

    async with db_pool.acquire() as conn:
        game = await conn.fetchrow(
            """
            INSERT INTO games (id, name, date, team_id, home_team_color, away_team_color)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id, name, date, team_id, home_team_color, away_team_color, created_at
            """,
            game_id, "Test Game", datetime.now().date(), uuid.UUID(test_team["id"]), "white", "dark"
        )

    return {
        "id": str(game["id"]),
        "name": game["name"],
        "date": str(game["date"]),
        "team_id": str(game["team_id"]),
        "home_team_color": game["home_team_color"],
        "away_team_color": game["away_team_color"],
        "created_at": game["created_at"]
    }


@pytest.fixture
async def test_video(db_pool, test_game) -> Dict:
    """Create a test video for the test game."""
    video_id = uuid.uuid4()

    async with db_pool.acquire() as conn:
        video = await conn.fetchrow(
            """
            INSERT INTO videos (id, game_id, filename, video_path)
            VALUES ($1, $2, $3, $4)
            RETURNING id, game_id, filename, video_path, uploaded_at
            """,
            video_id, uuid.UUID(test_game["id"]), "test_video.mp4", f"games/{test_game['id']}/{video_id}_test_video.mp4"
        )

    return {
        "id": str(video["id"]),
        "game_id": str(video["game_id"]),
        "filename": video["filename"],
        "video_path": video["video_path"],
        "uploaded_at": video["uploaded_at"]
    }


@pytest.fixture
async def test_clip(db_pool, test_game, test_video) -> Dict:
    """Create a test clip for the test video."""
    clip_id = uuid.uuid4()

    async with db_pool.acquire() as conn:
        clip = await conn.fetchrow(
            """
            INSERT INTO clips (id, game_id, video_id, start_time, end_time, tags, players, notes, status)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'completed')
            RETURNING id, game_id, video_id, start_time, end_time, tags, players, notes, clip_path, status, created_at
            """,
            clip_id, uuid.UUID(test_game["id"]), uuid.UUID(test_video["id"]),
            "00:10", "00:20", ["defense", "steal"], ["Test Player"], "Good defensive play"
        )

    return {
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
    }


@pytest.fixture
async def player_on_team(db_pool, test_team, test_player) -> Dict:
    """Add the test player to the test team."""
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO team_players (team_id, player_id)
            VALUES ($1, $2)
            """,
            uuid.UUID(test_team["id"]), uuid.UUID(test_player["id"])
        )

    return {"team_id": test_team["id"], "player_id": test_player["id"]}


@pytest.fixture
async def clip_assignment(db_pool, test_clip, test_player, test_coach, player_on_team) -> Dict:
    """Create a clip assignment for the test player."""
    assignment_id = uuid.uuid4()

    async with db_pool.acquire() as conn:
        assignment = await conn.fetchrow(
            """
            INSERT INTO clip_assignments (id, clip_id, player_id, assigned_by, message, priority)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id, clip_id, player_id, assigned_by, message, priority, viewed_at, acknowledged_at, created_at
            """,
            assignment_id, uuid.UUID(test_clip["id"]), uuid.UUID(test_player["id"]),
            uuid.UUID(test_coach["id"]), "Watch this defensive play", "normal"
        )

    return {
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


@pytest.fixture
async def parent_child_link(db_pool, test_parent, test_player) -> Dict:
    """Link the test parent to the test player."""
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO parent_links (parent_id, player_id, verified_at)
            VALUES ($1, $2, NOW())
            """,
            uuid.UUID(test_parent["id"]), uuid.UUID(test_player["id"])
        )

    return {"parent_id": test_parent["id"], "player_id": test_player["id"]}


@pytest.fixture
async def test_invite(db_pool, test_team, test_coach) -> Dict:
    """Create a test invite code."""
    import secrets
    invite_id = uuid.uuid4()
    code = secrets.token_urlsafe(16)

    async with db_pool.acquire() as conn:
        invite = await conn.fetchrow(
            """
            INSERT INTO invites (id, code, team_id, target_role, target_name, expires_at, created_by)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id, code, team_id, target_role, target_name, expires_at, created_by, created_at
            """,
            invite_id, code, uuid.UUID(test_team["id"]), "player", "New Player",
            datetime.utcnow() + timedelta(days=30), uuid.UUID(test_coach["id"])
        )

    return {
        "id": str(invite["id"]),
        "code": invite["code"],
        "team_id": str(invite["team_id"]),
        "target_role": invite["target_role"],
        "target_name": invite["target_name"],
        "expires_at": invite["expires_at"],
        "created_by": str(invite["created_by"]),
        "created_at": invite["created_at"]
    }
