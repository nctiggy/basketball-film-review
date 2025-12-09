"""
Integration tests for teams API endpoints.

Tests /teams/* endpoints including CRUD operations, roster, and coach management.
"""

import pytest
import uuid


@pytest.mark.integration
@pytest.mark.asyncio
class TestTeamsCRUD:
    """Test team CRUD operations."""

    async def test_create_team(self, async_client, coach_token):
        """Test creating a new team."""
        response = await async_client.post(
            "/teams",
            headers={"Authorization": f"Bearer {coach_token}"},
            json={
                "name": "New Team",
                "season": "2024-2025"
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Team"
        assert data["season"] == "2024-2025"
        assert "id" in data
        assert "created_at" in data

    async def test_list_teams(self, async_client, coach_token, test_team):
        """Test listing teams for a coach."""
        response = await async_client.get(
            "/teams",
            headers={"Authorization": f"Bearer {coach_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert any(team["id"] == test_team["id"] for team in data)

    async def test_get_team(self, async_client, coach_token, test_team):
        """Test getting a specific team."""
        response = await async_client.get(
            f"/teams/{test_team['id']}",
            headers={"Authorization": f"Bearer {coach_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_team["id"]
        assert data["name"] == test_team["name"]

    async def test_update_team(self, async_client, coach_token, test_team):
        """Test updating a team."""
        response = await async_client.put(
            f"/teams/{test_team['id']}",
            headers={"Authorization": f"Bearer {coach_token}"},
            json={
                "name": "Updated Team Name",
                "season": "2025"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Team Name"
        assert data["season"] == "2025"

    async def test_delete_team(self, async_client, coach_token, test_team):
        """Test deleting a team."""
        response = await async_client.delete(
            f"/teams/{test_team['id']}",
            headers={"Authorization": f"Bearer {coach_token}"}
        )

        assert response.status_code == 204

        # Verify team is gone
        get_response = await async_client.get(
            f"/teams/{test_team['id']}",
            headers={"Authorization": f"Bearer {coach_token}"}
        )
        assert get_response.status_code == 404

    async def test_player_cannot_create_team(self, async_client, player_token):
        """Test that players cannot create teams."""
        response = await async_client.post(
            "/teams",
            headers={"Authorization": f"Bearer {player_token}"},
            json={"name": "Player Team", "season": "2024"}
        )

        assert response.status_code == 403

    async def test_unauthenticated_cannot_list_teams(self, async_client):
        """Test that unauthenticated users cannot list teams."""
        response = await async_client.get("/teams")

        assert response.status_code == 401 or response.status_code == 403


@pytest.mark.integration
@pytest.mark.asyncio
class TestTeamRoster:
    """Test team roster management."""

    async def test_add_player_to_team(self, async_client, coach_token, test_team):
        """Test adding a player to team roster."""
        response = await async_client.post(
            f"/teams/{test_team['id']}/players",
            headers={"Authorization": f"Bearer {coach_token}"},
            json={
                "display_name": "New Player",
                "jersey_number": "23",
                "position": "PG"
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert "player" in data
        assert "invite" in data
        assert data["player"]["display_name"] == "New Player"
        assert data["invite"]["code"] is not None

    async def test_list_team_players(self, async_client, coach_token, test_team, player_on_team):
        """Test listing players on team roster."""
        response = await async_client.get(
            f"/teams/{test_team['id']}/players",
            headers={"Authorization": f"Bearer {coach_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    async def test_remove_player_from_team(self, async_client, coach_token, test_team, player_on_team, test_player):
        """Test removing a player from team roster."""
        response = await async_client.delete(
            f"/teams/{test_team['id']}/players/{test_player['id']}",
            headers={"Authorization": f"Bearer {coach_token}"}
        )

        assert response.status_code == 204

        # Verify player is removed
        list_response = await async_client.get(
            f"/teams/{test_team['id']}/players",
            headers={"Authorization": f"Bearer {coach_token}"}
        )
        players = list_response.json()
        assert not any(p["id"] == test_player["id"] for p in players)

    async def test_coach_without_access_cannot_add_player(self, async_client, db_pool, test_team):
        """Test that coaches without team access cannot add players."""
        # Create another coach
        from backend.auth import hash_password, create_access_token

        coach2_id = uuid.uuid4()
        password_hash = hash_password("password123")

        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO users (id, username, password_hash, display_name, role, auth_provider, status)
                VALUES ($1, $2, $3, $4, 'coach', 'local', 'active')
                """,
                coach2_id, "coach2", password_hash, "Coach 2"
            )

        coach2_token = create_access_token(str(coach2_id), "coach")

        response = await async_client.post(
            f"/teams/{test_team['id']}/players",
            headers={"Authorization": f"Bearer {coach2_token}"},
            json={"display_name": "New Player"}
        )

        assert response.status_code == 403


@pytest.mark.integration
@pytest.mark.asyncio
class TestTeamCoaches:
    """Test team coach management."""

    async def test_list_team_coaches(self, async_client, coach_token, test_team):
        """Test listing coaches for a team."""
        response = await async_client.get(
            f"/teams/{test_team['id']}/coaches",
            headers={"Authorization": f"Bearer {coach_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    async def test_add_coach_to_team(self, async_client, coach_token, test_team, db_pool):
        """Test adding an assistant coach to team."""
        # Create another coach
        from backend.auth import hash_password

        coach2_id = uuid.uuid4()
        password_hash = hash_password("password123")

        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO users (id, username, password_hash, display_name, role, auth_provider, status)
                VALUES ($1, $2, $3, $4, 'coach', 'local', 'active')
                """,
                coach2_id, "coach2", password_hash, "Coach 2"
            )

        response = await async_client.post(
            f"/teams/{test_team['id']}/coaches",
            headers={"Authorization": f"Bearer {coach_token}"},
            json={
                "coach_id": str(coach2_id),
                "role": "assistant"
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert data["id"] == str(coach2_id)
        assert data["role"] == "assistant"

    async def test_remove_coach_from_team(self, async_client, coach_token, test_team, db_pool):
        """Test removing a coach from team."""
        # Add another coach first
        from backend.auth import hash_password

        coach2_id = uuid.uuid4()
        password_hash = hash_password("password123")

        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO users (id, username, password_hash, display_name, role, auth_provider, status)
                VALUES ($1, $2, $3, $4, 'coach', 'local', 'active')
                """,
                coach2_id, "coach2", password_hash, "Coach 2"
            )
            await conn.execute(
                """
                INSERT INTO team_coaches (team_id, coach_id, role)
                VALUES ($1, $2, 'assistant')
                """,
                uuid.UUID(test_team["id"]), coach2_id
            )

        response = await async_client.delete(
            f"/teams/{test_team['id']}/coaches/{coach2_id}",
            headers={"Authorization": f"Bearer {coach_token}"}
        )

        assert response.status_code == 204

    async def test_cannot_remove_last_coach(self, async_client, coach_token, test_team, test_coach):
        """Test that the last coach cannot be removed from team."""
        response = await async_client.delete(
            f"/teams/{test_team['id']}/coaches/{test_coach['id']}",
            headers={"Authorization": f"Bearer {coach_token}"}
        )

        assert response.status_code == 400


@pytest.mark.integration
@pytest.mark.asyncio
class TestTeamAuthorization:
    """Test team access authorization."""

    async def test_coach_can_only_see_own_teams(self, async_client, db_pool):
        """Test that coaches can only see teams they're associated with."""
        from backend.auth import hash_password, create_access_token

        # Create two coaches and two teams
        coach1_id = uuid.uuid4()
        coach2_id = uuid.uuid4()
        team1_id = uuid.uuid4()
        team2_id = uuid.uuid4()

        password_hash = hash_password("password123")

        async with db_pool.acquire() as conn:
            # Create coaches
            await conn.execute(
                """
                INSERT INTO users (id, username, password_hash, display_name, role, auth_provider, status)
                VALUES ($1, $2, $3, $4, 'coach', 'local', 'active')
                """,
                coach1_id, "coach1_test", password_hash, "Coach 1"
            )
            await conn.execute(
                """
                INSERT INTO users (id, username, password_hash, display_name, role, auth_provider, status)
                VALUES ($1, $2, $3, $4, 'coach', 'local', 'active')
                """,
                coach2_id, "coach2_test", password_hash, "Coach 2"
            )

            # Create teams
            await conn.execute(
                """
                INSERT INTO teams (id, name, season, created_by)
                VALUES ($1, $2, $3, $4)
                """,
                team1_id, "Coach 1 Team", "2024", coach1_id
            )
            await conn.execute(
                """
                INSERT INTO teams (id, name, season, created_by)
                VALUES ($1, $2, $3, $4)
                """,
                team2_id, "Coach 2 Team", "2024", coach2_id
            )

            # Link coaches to teams
            await conn.execute(
                "INSERT INTO team_coaches (team_id, coach_id, role) VALUES ($1, $2, 'head')",
                team1_id, coach1_id
            )
            await conn.execute(
                "INSERT INTO team_coaches (team_id, coach_id, role) VALUES ($1, $2, 'head')",
                team2_id, coach2_id
            )

        coach1_token = create_access_token(str(coach1_id), "coach")

        # Coach 1 tries to access Coach 2's team
        response = await async_client.get(
            f"/teams/{team2_id}",
            headers={"Authorization": f"Bearer {coach1_token}"}
        )

        assert response.status_code == 403
