"""
Security tests for access control.

CRITICAL: These tests verify that users cannot access data they shouldn't.
This is the most important test file - all tests MUST pass.
"""

import pytest


@pytest.mark.security
@pytest.mark.asyncio
class TestPlayerAccessControl:
    """Test that players can only access their own data."""

    async def test_player_cannot_access_other_player_clips(self, async_client, player_token, player_2_token, test_player, test_player_2, test_clip, db_pool):
        """CRITICAL: Player A cannot access Player B's clips (by ID guessing)."""
        import uuid

        # Assign clip to player 2 only
        async with db_pool.acquire() as conn:
            # Get team_id from game
            game = await conn.fetchrow("SELECT team_id FROM games WHERE id = $1", uuid.UUID(test_clip["game_id"]))
            team_id = game["team_id"]

            # Add player 2 to team
            await conn.execute(
                "INSERT INTO team_players (team_id, player_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                team_id, uuid.UUID(test_player_2["id"])
            )

            # Assign clip to player 2
            await conn.execute(
                """
                INSERT INTO clip_assignments (clip_id, player_id, assigned_by)
                VALUES ($1, $2, $3)
                """,
                uuid.UUID(test_clip["id"]), uuid.UUID(test_player_2["id"]), uuid.UUID(test_player["id"])
            )

        # Player 1 tries to access Player 2's clip assignments
        response = await async_client.get(
            f"/clips/{test_clip['id']}/assignments",
            headers={"Authorization": f"Bearer {player_token}"}
        )

        # Player 1 should either get empty list or no access
        if response.status_code == 200:
            assignments = response.json()
            # Should not see player 2's assignment
            assert not any(a["player_id"] == test_player_2["id"] for a in assignments)

    async def test_player_cannot_stream_unassigned_clip(self, async_client, player_token, test_clip, db_pool):
        """CRITICAL: Player cannot stream clips not assigned to them."""
        import uuid

        # Ensure clip has completed status and path
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE clips
                SET status = 'completed', clip_path = $1
                WHERE id = $2
                """,
                f"clips/{test_clip['id']}.mp4",
                uuid.UUID(test_clip["id"])
            )

        # Try to stream clip not assigned to this player
        response = await async_client.get(
            f"/clips/{test_clip['id']}/stream",
            headers={"Authorization": f"Bearer {player_token}"}
        )

        assert response.status_code == 403

    async def test_player_cannot_access_other_player_stats(self, async_client, player_token, test_player_2, db_pool, test_game):
        """CRITICAL: Players cannot access other players' stats."""
        import uuid

        # Add stats for player 2
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO player_game_stats (game_id, player_id, points)
                VALUES ($1, $2, 30)
                """,
                uuid.UUID(test_game["id"]), uuid.UUID(test_player_2["id"])
            )

        # Player 1's /me/stats should not include player 2's stats
        response = await async_client.get(
            "/me/stats",
            headers={"Authorization": f"Bearer {player_token}"}
        )

        assert response.status_code == 200
        stats = response.json()
        # Should not include any stats with 30 points (player 2's stats)
        assert not any(s.get("points") == 30 for s in stats)

    async def test_player_cannot_mark_other_player_clip_as_viewed(self, async_client, player_token, test_player_2, test_clip, db_pool):
        """CRITICAL: Player cannot mark another player's clip assignment as viewed."""
        import uuid

        # Assign clip to player 2
        async with db_pool.acquire() as conn:
            # Get team_id from game
            game = await conn.fetchrow("SELECT team_id FROM games WHERE id = $1", uuid.UUID(test_clip["game_id"]))
            team_id = game["team_id"]

            # Add player 2 to team
            await conn.execute(
                "INSERT INTO team_players (team_id, player_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                team_id, uuid.UUID(test_player_2["id"])
            )

            await conn.execute(
                """
                INSERT INTO clip_assignments (clip_id, player_id, assigned_by)
                VALUES ($1, $2, $3)
                """,
                uuid.UUID(test_clip["id"]), uuid.UUID(test_player_2["id"]), uuid.UUID(test_player_2["id"])
            )

        # Player 1 tries to mark player 2's clip as viewed
        response = await async_client.post(
            f"/me/clips/{test_clip['id']}/viewed",
            headers={"Authorization": f"Bearer {player_token}"}
        )

        # Should fail with 404 (not found) or 403 (forbidden)
        assert response.status_code in [403, 404]


@pytest.mark.security
@pytest.mark.asyncio
class TestPlayerEndpointAccess:
    """Test that players cannot access coach-only endpoints."""

    async def test_player_cannot_access_teams_endpoints(self, async_client, player_token):
        """CRITICAL: Players should not access /teams/* endpoints."""
        # Try to list teams
        response = await async_client.get(
            "/teams",
            headers={"Authorization": f"Bearer {player_token}"}
        )
        assert response.status_code == 403

    async def test_player_cannot_create_team(self, async_client, player_token):
        """CRITICAL: Players cannot create teams."""
        response = await async_client.post(
            "/teams",
            headers={"Authorization": f"Bearer {player_token}"},
            json={"name": "Hacked Team", "season": "2024"}
        )
        assert response.status_code == 403

    async def test_player_cannot_assign_clips(self, async_client, player_token, test_clip, test_player_2):
        """CRITICAL: Players cannot assign clips to other players."""
        response = await async_client.post(
            f"/clips/{test_clip['id']}/assign",
            headers={"Authorization": f"Bearer {player_token}"},
            json={
                "player_ids": [test_player_2["id"]],
                "message": "Unauthorized assignment"
            }
        )
        assert response.status_code == 403

    async def test_player_cannot_remove_assignments(self, async_client, player_token, clip_assignment, test_player):
        """CRITICAL: Players cannot remove clip assignments."""
        response = await async_client.delete(
            f"/clips/{clip_assignment['clip_id']}/assignments/{test_player['id']}",
            headers={"Authorization": f"Bearer {player_token}"}
        )
        assert response.status_code == 403

    async def test_player_cannot_modify_team_roster(self, async_client, player_token, test_team, test_player_2):
        """CRITICAL: Players cannot add or remove players from team."""
        response = await async_client.post(
            f"/teams/{test_team['id']}/players",
            headers={"Authorization": f"Bearer {player_token}"},
            json={"display_name": "New Player"}
        )
        assert response.status_code == 403

        response = await async_client.delete(
            f"/teams/{test_team['id']}/players/{test_player_2['id']}",
            headers={"Authorization": f"Bearer {player_token}"}
        )
        assert response.status_code == 403


@pytest.mark.security
@pytest.mark.asyncio
class TestParentAccessControl:
    """Test that parents can only access their linked children's data."""

    async def test_parent_cannot_access_non_linked_child_clips(self, async_client, parent_token, test_player_2, test_clip, db_pool):
        """CRITICAL: Parent cannot access non-linked child's clips."""
        import uuid

        # Assign clip to non-linked player
        async with db_pool.acquire() as conn:
            # Get team_id from game
            game = await conn.fetchrow("SELECT team_id FROM games WHERE id = $1", uuid.UUID(test_clip["game_id"]))
            team_id = game["team_id"]

            # Add player 2 to team
            await conn.execute(
                "INSERT INTO team_players (team_id, player_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                team_id, uuid.UUID(test_player_2["id"])
            )

            await conn.execute(
                """
                INSERT INTO clip_assignments (clip_id, player_id, assigned_by)
                VALUES ($1, $2, $3)
                """,
                uuid.UUID(test_clip["id"]), uuid.UUID(test_player_2["id"]), uuid.UUID(test_player_2["id"])
            )

        # Parent tries to access non-linked child's clips
        response = await async_client.get(
            f"/me/children/{test_player_2['id']}/clips",
            headers={"Authorization": f"Bearer {parent_token}"}
        )

        assert response.status_code == 403

    async def test_parent_cannot_access_non_linked_child_stats(self, async_client, parent_token, test_player_2):
        """CRITICAL: Parent cannot access non-linked child's stats."""
        response = await async_client.get(
            f"/me/children/{test_player_2['id']}/stats",
            headers={"Authorization": f"Bearer {parent_token}"}
        )

        assert response.status_code == 403

    async def test_parent_cannot_stream_non_linked_child_clip(self, async_client, parent_token, test_player_2, test_clip, db_pool):
        """CRITICAL: Parent cannot stream clips assigned to non-linked children."""
        import uuid

        # Assign clip to non-linked player and set it as completed
        async with db_pool.acquire() as conn:
            # Get team_id from game
            game = await conn.fetchrow("SELECT team_id FROM games WHERE id = $1", uuid.UUID(test_clip["game_id"]))
            team_id = game["team_id"]

            # Add player 2 to team
            await conn.execute(
                "INSERT INTO team_players (team_id, player_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                team_id, uuid.UUID(test_player_2["id"])
            )

            await conn.execute(
                """
                INSERT INTO clip_assignments (clip_id, player_id, assigned_by)
                VALUES ($1, $2, $3)
                """,
                uuid.UUID(test_clip["id"]), uuid.UUID(test_player_2["id"]), uuid.UUID(test_player_2["id"])
            )

            await conn.execute(
                """
                UPDATE clips
                SET status = 'completed', clip_path = $1
                WHERE id = $2
                """,
                f"clips/{test_clip['id']}.mp4",
                uuid.UUID(test_clip["id"])
            )

        # Parent tries to stream clip
        response = await async_client.get(
            f"/clips/{test_clip['id']}/stream",
            headers={"Authorization": f"Bearer {parent_token}"}
        )

        assert response.status_code == 403

    async def test_parent_cannot_access_coach_endpoints(self, async_client, parent_token):
        """CRITICAL: Parents should not access coach endpoints."""
        response = await async_client.get(
            "/teams",
            headers={"Authorization": f"Bearer {parent_token}"}
        )
        assert response.status_code == 403

    async def test_parent_cannot_access_player_action_endpoints(self, async_client, parent_token, clip_assignment):
        """CRITICAL: Parents cannot mark clips as viewed (read-only access)."""
        response = await async_client.post(
            f"/me/clips/{clip_assignment['clip_id']}/viewed",
            headers={"Authorization": f"Bearer {parent_token}"}
        )
        assert response.status_code == 403


@pytest.mark.security
@pytest.mark.asyncio
class TestCoachAccessControl:
    """Test coach access control boundaries."""

    async def test_coach_cannot_access_other_team_data(self, async_client, db_pool):
        """CRITICAL: Coach cannot access teams they're not associated with."""
        from backend.auth import hash_password, create_access_token
        import uuid

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
                coach1_id, "coach1_sec", password_hash, "Coach 1"
            )
            await conn.execute(
                """
                INSERT INTO users (id, username, password_hash, display_name, role, auth_provider, status)
                VALUES ($1, $2, $3, $4, 'coach', 'local', 'active')
                """,
                coach2_id, "coach2_sec", password_hash, "Coach 2"
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

    async def test_coach_cannot_modify_other_team_roster(self, async_client, db_pool):
        """CRITICAL: Coach cannot modify roster of team they don't manage."""
        from backend.auth import hash_password, create_access_token
        import uuid

        # Setup similar to above
        coach1_id = uuid.uuid4()
        coach2_id = uuid.uuid4()
        team2_id = uuid.uuid4()

        password_hash = hash_password("password123")

        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO users (id, username, password_hash, display_name, role, auth_provider, status)
                VALUES ($1, $2, $3, $4, 'coach', 'local', 'active')
                """,
                coach1_id, "coach1_mod", password_hash, "Coach 1"
            )
            await conn.execute(
                """
                INSERT INTO users (id, username, password_hash, display_name, role, auth_provider, status)
                VALUES ($1, $2, $3, $4, 'coach', 'local', 'active')
                """,
                coach2_id, "coach2_mod", password_hash, "Coach 2"
            )

            await conn.execute(
                """
                INSERT INTO teams (id, name, season, created_by)
                VALUES ($1, $2, $3, $4)
                """,
                team2_id, "Coach 2 Team", "2024", coach2_id
            )

            await conn.execute(
                "INSERT INTO team_coaches (team_id, coach_id, role) VALUES ($1, $2, 'head')",
                team2_id, coach2_id
            )

        coach1_token = create_access_token(str(coach1_id), "coach")

        # Coach 1 tries to add player to Coach 2's team
        response = await async_client.post(
            f"/teams/{team2_id}/players",
            headers={"Authorization": f"Bearer {coach1_token}"},
            json={"display_name": "Unauthorized Player"}
        )

        assert response.status_code == 403


@pytest.mark.security
@pytest.mark.asyncio
class TestTokenValidation:
    """Test token validation and expiration."""

    async def test_expired_token_rejected(self, async_client):
        """CRITICAL: Expired tokens should be rejected."""
        from backend.auth.jwt import JWT_SECRET, JWT_ALGORITHM
        import jwt
        from datetime import datetime, timedelta

        # Create an expired token
        payload = {
            "sub": "123e4567-e89b-12d3-a456-426614174000",
            "role": "coach",
            "type": "access",
            "exp": datetime.utcnow() - timedelta(hours=1),  # Expired 1 hour ago
            "iat": datetime.utcnow() - timedelta(hours=25)
        }
        expired_token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

        response = await async_client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"}
        )

        assert response.status_code == 401

    async def test_invalid_token_rejected(self, async_client):
        """CRITICAL: Invalid tokens should be rejected."""
        response = await async_client.get(
            "/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"}
        )

        assert response.status_code in [401, 500]

    async def test_missing_token_rejected(self, async_client):
        """CRITICAL: Requests without tokens should be rejected."""
        response = await async_client.get("/auth/me")

        assert response.status_code in [401, 403]

    async def test_wrong_token_type_rejected(self, async_client, test_coach):
        """CRITICAL: Using refresh token as access token should be rejected."""
        from backend.auth import create_refresh_token

        # Create a refresh token
        refresh_token = create_refresh_token(test_coach["id"])

        # Try to use it as access token
        response = await async_client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {refresh_token}"}
        )

        # Should fail because type is 'refresh' not 'access'
        assert response.status_code in [401, 403]


@pytest.mark.security
@pytest.mark.asyncio
class TestIDGuessing:
    """Test protection against ID guessing attacks."""

    async def test_cannot_guess_clip_ids(self, async_client, player_token):
        """CRITICAL: Random clip IDs should not grant access."""
        fake_clip_id = "00000000-0000-0000-0000-000000000000"

        response = await async_client.get(
            f"/clips/{fake_clip_id}/stream",
            headers={"Authorization": f"Bearer {player_token}"}
        )

        assert response.status_code in [403, 404]

    async def test_cannot_guess_team_ids(self, async_client, coach_token):
        """CRITICAL: Random team IDs should not grant access."""
        fake_team_id = "00000000-0000-0000-0000-000000000000"

        response = await async_client.get(
            f"/teams/{fake_team_id}",
            headers={"Authorization": f"Bearer {coach_token}"}
        )

        assert response.status_code in [403, 404]

    async def test_cannot_guess_player_ids(self, async_client, parent_token):
        """CRITICAL: Random player IDs should not grant access."""
        fake_player_id = "00000000-0000-0000-0000-000000000000"

        response = await async_client.get(
            f"/me/children/{fake_player_id}/clips",
            headers={"Authorization": f"Bearer {parent_token}"}
        )

        assert response.status_code in [403, 404]
