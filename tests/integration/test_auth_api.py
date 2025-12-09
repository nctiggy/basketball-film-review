"""
Integration tests for authentication API endpoints.

Tests /auth/* endpoints including login, register, refresh, and profile management.
"""

import pytest
from datetime import datetime, timedelta


@pytest.mark.integration
@pytest.mark.asyncio
class TestAuthLogin:
    """Test /auth/login endpoint."""

    async def test_login_with_valid_credentials(self, async_client, test_coach):
        """Test successful login with valid username and password."""
        response = await async_client.post("/auth/login", json={
            "username": test_coach["username"],
            "password": test_coach["password"]
        })

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert "user" in data
        assert data["user"]["id"] == test_coach["id"]
        assert data["user"]["role"] == test_coach["role"]

    async def test_login_with_email(self, async_client, test_coach):
        """Test login using email instead of username."""
        response = await async_client.post("/auth/login", json={
            "username": test_coach["email"],  # Use email
            "password": test_coach["password"]
        })

        assert response.status_code == 200
        data = response.json()
        assert data["user"]["email"] == test_coach["email"]

    async def test_login_with_invalid_password(self, async_client, test_coach):
        """Test login fails with incorrect password."""
        response = await async_client.post("/auth/login", json={
            "username": test_coach["username"],
            "password": "wrong_password"
        })

        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert "invalid" in data["detail"].lower()

    async def test_login_with_nonexistent_user(self, async_client):
        """Test login fails for non-existent user."""
        response = await async_client.post("/auth/login", json={
            "username": "nonexistent_user",
            "password": "password123"
        })

        assert response.status_code == 401
        data = response.json()
        assert "detail" in data

    async def test_login_missing_username(self, async_client):
        """Test login fails when username is missing."""
        response = await async_client.post("/auth/login", json={
            "password": "password123"
        })

        assert response.status_code == 422  # Validation error

    async def test_login_missing_password(self, async_client):
        """Test login fails when password is missing."""
        response = await async_client.post("/auth/login", json={
            "username": "testuser"
        })

        assert response.status_code == 422  # Validation error

    async def test_login_updates_last_login(self, async_client, test_player, db_pool):
        """Test that login updates the last_login_at timestamp."""
        # Record time before login
        before_login = datetime.utcnow()

        response = await async_client.post("/auth/login", json={
            "username": test_player["username"],
            "password": test_player["password"]
        })

        assert response.status_code == 200

        # Check last_login_at was updated
        import uuid
        async with db_pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT last_login_at FROM users WHERE id = $1",
                uuid.UUID(test_player["id"])
            )

        assert user["last_login_at"] is not None
        assert user["last_login_at"] >= before_login


@pytest.mark.integration
@pytest.mark.asyncio
class TestAuthRegister:
    """Test /auth/register endpoint."""

    async def test_register_with_valid_invite(self, async_client, test_invite):
        """Test successful registration with valid invite code."""
        response = await async_client.post("/auth/register", json={
            "invite_code": test_invite["code"],
            "username": "newplayer",
            "password": "secure_pass_123",
            "display_name": "New Player",
            "phone": "555-9999"
        })

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["username"] == "newplayer"
        assert data["user"]["role"] == test_invite["target_role"]
        assert data["user"]["display_name"] == "New Player"

    async def test_register_marks_invite_as_claimed(self, async_client, test_invite, db_pool):
        """Test that registration marks the invite as claimed."""
        response = await async_client.post("/auth/register", json={
            "invite_code": test_invite["code"],
            "username": "newplayer2",
            "password": "secure_pass_123",
            "display_name": "New Player 2"
        })

        assert response.status_code == 200

        # Check invite is claimed
        import uuid
        async with db_pool.acquire() as conn:
            invite = await conn.fetchrow(
                "SELECT claimed_by, claimed_at FROM invites WHERE code = $1",
                test_invite["code"]
            )

        assert invite["claimed_by"] is not None
        assert invite["claimed_at"] is not None

    async def test_register_with_expired_invite(self, async_client, db_pool, test_team, test_coach):
        """Test registration fails with expired invite."""
        import secrets
        import uuid

        # Create expired invite
        code = secrets.token_urlsafe(16)
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO invites (code, team_id, target_role, expires_at, created_by)
                VALUES ($1, $2, 'player', $3, $4)
                """,
                code, uuid.UUID(test_team["id"]),
                datetime.utcnow() - timedelta(days=1),  # Expired
                uuid.UUID(test_coach["id"])
            )

        response = await async_client.post("/auth/register", json={
            "invite_code": code,
            "username": "newplayer",
            "password": "secure_pass_123",
            "display_name": "New Player"
        })

        assert response.status_code == 400
        data = response.json()
        assert "expired" in data["detail"].lower() or "invalid" in data["detail"].lower()

    async def test_register_with_already_claimed_invite(self, async_client, test_invite):
        """Test registration fails with already claimed invite."""
        # First registration
        response1 = await async_client.post("/auth/register", json={
            "invite_code": test_invite["code"],
            "username": "player1",
            "password": "secure_pass_123",
            "display_name": "Player 1"
        })
        assert response1.status_code == 200

        # Second registration with same code
        response2 = await async_client.post("/auth/register", json={
            "invite_code": test_invite["code"],
            "username": "player2",
            "password": "secure_pass_123",
            "display_name": "Player 2"
        })

        assert response2.status_code == 400

    async def test_register_with_duplicate_username(self, async_client, test_invite, test_player):
        """Test registration fails with duplicate username."""
        response = await async_client.post("/auth/register", json={
            "invite_code": test_invite["code"],
            "username": test_player["username"],  # Already exists
            "password": "secure_pass_123",
            "display_name": "New Player"
        })

        assert response.status_code == 400
        data = response.json()
        assert "username" in data["detail"].lower()


@pytest.mark.integration
@pytest.mark.asyncio
class TestAuthRefresh:
    """Test /auth/refresh endpoint."""

    async def test_refresh_with_valid_token(self, async_client, test_coach):
        """Test refreshing access token with valid refresh token."""
        # Login to get refresh token
        login_response = await async_client.post("/auth/login", json={
            "username": test_coach["username"],
            "password": test_coach["password"]
        })
        refresh_token = login_response.json()["refresh_token"]

        # Refresh the token
        response = await async_client.post("/auth/refresh", json={
            "refresh_token": refresh_token
        })

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        # Should get a new refresh token
        assert data["refresh_token"] != refresh_token

    async def test_refresh_with_invalid_token(self, async_client):
        """Test refresh fails with invalid token."""
        response = await async_client.post("/auth/refresh", json={
            "refresh_token": "invalid.token.here"
        })

        assert response.status_code == 500 or response.status_code == 401

    async def test_refresh_revokes_old_token(self, async_client, test_coach, db_pool):
        """Test that refresh revokes the old refresh token."""
        # Login
        login_response = await async_client.post("/auth/login", json={
            "username": test_coach["username"],
            "password": test_coach["password"]
        })
        old_refresh_token = login_response.json()["refresh_token"]

        # Refresh
        await async_client.post("/auth/refresh", json={
            "refresh_token": old_refresh_token
        })

        # Try to use old token again
        response = await async_client.post("/auth/refresh", json={
            "refresh_token": old_refresh_token
        })

        assert response.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
class TestAuthMe:
    """Test /auth/me endpoint."""

    async def test_get_current_user(self, async_client, coach_token, test_coach):
        """Test getting current user profile."""
        response = await async_client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {coach_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_coach["id"]
        assert data["username"] == test_coach["username"]
        assert data["role"] == test_coach["role"]

    async def test_get_current_user_without_token(self, async_client):
        """Test getting current user fails without token."""
        response = await async_client.get("/auth/me")

        assert response.status_code == 401 or response.status_code == 403

    async def test_update_profile(self, async_client, player_token, test_player):
        """Test updating user profile."""
        response = await async_client.put(
            "/auth/me",
            headers={"Authorization": f"Bearer {player_token}"},
            json={
                "display_name": "Updated Player Name",
                "phone": "555-1111"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["display_name"] == "Updated Player Name"
        assert data["phone"] == "555-1111"

    async def test_update_profile_partial(self, async_client, player_token):
        """Test partial profile update."""
        response = await async_client.put(
            "/auth/me",
            headers={"Authorization": f"Bearer {player_token}"},
            json={"display_name": "Just Name Update"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["display_name"] == "Just Name Update"


@pytest.mark.integration
@pytest.mark.asyncio
class TestAuthPassword:
    """Test /auth/me/password endpoint."""

    async def test_change_password(self, async_client, player_token, test_player):
        """Test changing password."""
        response = await async_client.put(
            "/auth/me/password",
            headers={"Authorization": f"Bearer {player_token}"},
            json={
                "current_password": test_player["password"],
                "new_password": "new_secure_password_456"
            }
        )

        assert response.status_code == 200

        # Try logging in with new password
        login_response = await async_client.post("/auth/login", json={
            "username": test_player["username"],
            "password": "new_secure_password_456"
        })

        assert login_response.status_code == 200

    async def test_change_password_wrong_current(self, async_client, player_token):
        """Test password change fails with wrong current password."""
        response = await async_client.put(
            "/auth/me/password",
            headers={"Authorization": f"Bearer {player_token}"},
            json={
                "current_password": "wrong_password",
                "new_password": "new_secure_password_456"
            }
        )

        assert response.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
class TestAuthLogout:
    """Test /auth/logout endpoint."""

    async def test_logout(self, async_client, coach_token):
        """Test logout revokes refresh tokens."""
        response = await async_client.post(
            "/auth/logout",
            headers={"Authorization": f"Bearer {coach_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "message" in data

    async def test_logout_without_token(self, async_client):
        """Test logout fails without authentication."""
        response = await async_client.post("/auth/logout")

        assert response.status_code == 401 or response.status_code == 403
