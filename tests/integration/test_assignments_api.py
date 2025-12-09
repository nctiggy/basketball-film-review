"""
Integration tests for clip assignment API endpoints.

Tests /clips/{id}/assign and assignment management endpoints.
"""

import pytest


@pytest.mark.integration
@pytest.mark.asyncio
class TestClipAssignments:
    """Test clip assignment operations."""

    async def test_assign_clip_to_player(self, async_client, coach_token, test_clip, test_player, player_on_team):
        """Test assigning a clip to a player."""
        response = await async_client.post(
            f"/clips/{test_clip['id']}/assign",
            headers={"Authorization": f"Bearer {coach_token}"},
            json={
                "player_ids": [test_player["id"]],
                "message": "Great defensive play!",
                "priority": "high"
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["clip_id"] == test_clip["id"]
        assert data[0]["player_id"] == test_player["id"]
        assert data[0]["message"] == "Great defensive play!"
        assert data[0]["priority"] == "high"

    async def test_assign_clip_to_multiple_players(self, async_client, coach_token, test_clip, test_player, test_player_2, db_pool):
        """Test assigning a clip to multiple players."""
        import uuid
        # Add both players to team
        async with db_pool.acquire() as conn:
            # Get team_id from game
            game = await conn.fetchrow("SELECT team_id FROM games WHERE id = $1", uuid.UUID(test_clip["game_id"]))
            team_id = game["team_id"]

            # Add players to team
            await conn.execute(
                "INSERT INTO team_players (team_id, player_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                team_id, uuid.UUID(test_player["id"])
            )
            await conn.execute(
                "INSERT INTO team_players (team_id, player_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                team_id, uuid.UUID(test_player_2["id"])
            )

        response = await async_client.post(
            f"/clips/{test_clip['id']}/assign",
            headers={"Authorization": f"Bearer {coach_token}"},
            json={
                "player_ids": [test_player["id"], test_player_2["id"]],
                "message": "Watch this play together"
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert len(data) == 2

    async def test_list_clip_assignments_as_coach(self, async_client, coach_token, clip_assignment):
        """Test listing assignments for a clip as a coach."""
        response = await async_client.get(
            f"/clips/{clip_assignment['clip_id']}/assignments",
            headers={"Authorization": f"Bearer {coach_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert data[0]["clip_id"] == clip_assignment["clip_id"]

    async def test_list_clip_assignments_as_player(self, async_client, player_token, clip_assignment, test_player):
        """Test listing assignments as a player (should only see own assignment)."""
        response = await async_client.get(
            f"/clips/{clip_assignment['clip_id']}/assignments",
            headers={"Authorization": f"Bearer {player_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Player should only see their own assignment
        assert all(a["player_id"] == test_player["id"] for a in data)

    async def test_remove_clip_assignment(self, async_client, coach_token, clip_assignment, test_player):
        """Test removing a clip assignment."""
        response = await async_client.delete(
            f"/clips/{clip_assignment['clip_id']}/assignments/{test_player['id']}",
            headers={"Authorization": f"Bearer {coach_token}"}
        )

        assert response.status_code == 204

        # Verify assignment is removed
        list_response = await async_client.get(
            f"/clips/{clip_assignment['clip_id']}/assignments",
            headers={"Authorization": f"Bearer {coach_token}"}
        )
        assignments = list_response.json()
        assert not any(a["player_id"] == test_player["id"] for a in assignments)

    async def test_player_cannot_assign_clips(self, async_client, player_token, test_clip, test_player_2):
        """Test that players cannot assign clips."""
        response = await async_client.post(
            f"/clips/{test_clip['id']}/assign",
            headers={"Authorization": f"Bearer {player_token}"},
            json={
                "player_ids": [test_player_2["id"]],
                "message": "Check this out"
            }
        )

        assert response.status_code == 403

    async def test_assign_clip_to_player_not_on_team(self, async_client, coach_token, test_clip, test_player_2):
        """Test assigning clip to player not on the team fails."""
        response = await async_client.post(
            f"/clips/{test_clip['id']}/assign",
            headers={"Authorization": f"Bearer {coach_token}"},
            json={
                "player_ids": [test_player_2["id"]],  # Not on the team
                "message": "Check this"
            }
        )

        assert response.status_code == 400
        data = response.json()
        assert "not on this team" in data["detail"].lower()

    async def test_reassign_clip_updates_assignment(self, async_client, coach_token, clip_assignment, test_player):
        """Test that reassigning a clip to the same player updates the assignment."""
        # Assign again with different message
        response = await async_client.post(
            f"/clips/{clip_assignment['clip_id']}/assign",
            headers={"Authorization": f"Bearer {coach_token}"},
            json={
                "player_ids": [test_player["id"]],
                "message": "Updated message!",
                "priority": "low"
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert data[0]["message"] == "Updated message!"
        assert data[0]["priority"] == "low"


@pytest.mark.integration
@pytest.mark.asyncio
class TestAssignmentAuthorization:
    """Test authorization for assignment operations."""

    async def test_coach_without_team_access_cannot_assign(self, async_client, db_pool, test_clip, test_player):
        """Test that coach without team access cannot assign clips."""
        from backend.auth import hash_password, create_access_token
        import uuid

        # Create another coach
        coach2_id = uuid.uuid4()
        password_hash = hash_password("password123")

        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO users (id, username, password_hash, display_name, role, auth_provider, status)
                VALUES ($1, $2, $3, $4, 'coach', 'local', 'active')
                """,
                coach2_id, "coach2_no_access", password_hash, "Coach Without Access"
            )

        coach2_token = create_access_token(str(coach2_id), "coach")

        response = await async_client.post(
            f"/clips/{test_clip['id']}/assign",
            headers={"Authorization": f"Bearer {coach2_token}"},
            json={
                "player_ids": [test_player["id"]],
                "message": "Test"
            }
        )

        assert response.status_code == 403

    async def test_player_cannot_remove_assignments(self, async_client, player_token, clip_assignment, test_player):
        """Test that players cannot remove assignments."""
        response = await async_client.delete(
            f"/clips/{clip_assignment['clip_id']}/assignments/{test_player['id']}",
            headers={"Authorization": f"Bearer {player_token}"}
        )

        assert response.status_code == 403
