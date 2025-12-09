"""
Integration tests for player-specific API endpoints.

Tests /me/* endpoints for player functionality.
"""

import pytest


@pytest.mark.integration
@pytest.mark.asyncio
class TestPlayerClips:
    """Test /me/clips endpoint for players."""

    async def test_player_get_assigned_clips(self, async_client, player_token, clip_assignment):
        """Test player can get their assigned clips."""
        response = await async_client.get(
            "/me/clips",
            headers={"Authorization": f"Bearer {player_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert data[0]["id"] == clip_assignment["clip_id"]
        assert data[0]["assignment_id"] == clip_assignment["id"]

    async def test_player_only_sees_own_clips(self, async_client, player_token, player_2_token, test_clip, test_player, test_player_2, db_pool):
        """Test players only see clips assigned to them."""
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
                uuid.UUID(test_clip["id"]), uuid.UUID(test_player_2["id"]), uuid.UUID(test_player["id"])  # Use any user ID
            )

        # Player 1 should not see the clip
        response1 = await async_client.get(
            "/me/clips",
            headers={"Authorization": f"Bearer {player_token}"}
        )
        clips1 = response1.json()
        assert not any(c["id"] == test_clip["id"] for c in clips1)

        # Player 2 should see the clip
        response2 = await async_client.get(
            "/me/clips",
            headers={"Authorization": f"Bearer {player_2_token}"}
        )
        clips2 = response2.json()
        assert any(c["id"] == test_clip["id"] for c in clips2)

    async def test_coach_cannot_access_player_clips_endpoint(self, async_client, coach_token):
        """Test coaches cannot access /me/clips endpoint."""
        response = await async_client.get(
            "/me/clips",
            headers={"Authorization": f"Bearer {coach_token}"}
        )

        assert response.status_code == 403

    async def test_mark_clip_as_viewed(self, async_client, player_token, clip_assignment):
        """Test player can mark clip as viewed."""
        response = await async_client.post(
            f"/me/clips/{clip_assignment['clip_id']}/viewed",
            headers={"Authorization": f"Bearer {player_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "viewed_at" in data

        # Verify viewed_at is set in database
        clips_response = await async_client.get(
            "/me/clips",
            headers={"Authorization": f"Bearer {player_token}"}
        )
        clips = clips_response.json()
        clip = next(c for c in clips if c["id"] == clip_assignment["clip_id"])
        assert clip["viewed_at"] is not None

    async def test_acknowledge_clip(self, async_client, player_token, clip_assignment):
        """Test player can acknowledge clip."""
        response = await async_client.post(
            f"/me/clips/{clip_assignment['clip_id']}/acknowledge",
            headers={"Authorization": f"Bearer {player_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "acknowledged_at" in data

    async def test_acknowledge_also_marks_viewed(self, async_client, player_token, clip_assignment):
        """Test that acknowledging a clip also marks it as viewed."""
        response = await async_client.post(
            f"/me/clips/{clip_assignment['clip_id']}/acknowledge",
            headers={"Authorization": f"Bearer {player_token}"}
        )

        assert response.status_code == 200

        # Check that both viewed_at and acknowledged_at are set
        clips_response = await async_client.get(
            "/me/clips",
            headers={"Authorization": f"Bearer {player_token}"}
        )
        clips = clips_response.json()
        clip = next(c for c in clips if c["id"] == clip_assignment["clip_id"])
        assert clip["viewed_at"] is not None
        assert clip["acknowledged_at"] is not None

    async def test_player_cannot_mark_unassigned_clip(self, async_client, player_token, test_clip):
        """Test player cannot mark unassigned clip as viewed."""
        response = await async_client.post(
            f"/me/clips/{test_clip['id']}/viewed",
            headers={"Authorization": f"Bearer {player_token}"}
        )

        assert response.status_code == 404


@pytest.mark.integration
@pytest.mark.asyncio
class TestPlayerStats:
    """Test /me/stats endpoints for players."""

    async def test_player_get_own_stats(self, async_client, player_token, test_player, db_pool, test_game):
        """Test player can get their own stats."""
        import uuid

        # Add stats for player
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO player_game_stats (game_id, player_id, points, field_goals_made, field_goals_attempted)
                VALUES ($1, $2, 15, 6, 12)
                """,
                uuid.UUID(test_game["id"]), uuid.UUID(test_player["id"])
            )

        response = await async_client.get(
            "/me/stats",
            headers={"Authorization": f"Bearer {player_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert data[0]["points"] == 15

    async def test_player_only_sees_own_stats(self, async_client, player_token, player_2_token, test_player, test_player_2, db_pool, test_game):
        """Test players only see their own stats."""
        import uuid

        # Add stats for both players
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO player_game_stats (game_id, player_id, points)
                VALUES ($1, $2, 20)
                """,
                uuid.UUID(test_game["id"]), uuid.UUID(test_player["id"])
            )
            await conn.execute(
                """
                INSERT INTO player_game_stats (game_id, player_id, points)
                VALUES ($1, $2, 25)
                """,
                uuid.UUID(test_game["id"]), uuid.UUID(test_player_2["id"])
            )

        # Player 1 should only see their stats
        response1 = await async_client.get(
            "/me/stats",
            headers={"Authorization": f"Bearer {player_token}"}
        )
        stats1 = response1.json()
        assert all(s["points"] == 20 for s in stats1)

        # Player 2 should only see their stats
        response2 = await async_client.get(
            "/me/stats",
            headers={"Authorization": f"Bearer {player_2_token}"}
        )
        stats2 = response2.json()
        assert all(s["points"] == 25 for s in stats2)

    async def test_get_season_stats(self, async_client, player_token, test_player, db_pool, test_game):
        """Test getting aggregated season stats."""
        import uuid

        # Add multiple games of stats
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO player_game_stats
                (game_id, player_id, points, field_goals_made, field_goals_attempted, assists, offensive_rebounds, defensive_rebounds)
                VALUES ($1, $2, 20, 8, 15, 5, 2, 4)
                """,
                uuid.UUID(test_game["id"]), uuid.UUID(test_player["id"])
            )

        response = await async_client.get(
            "/me/stats/season",
            headers={"Authorization": f"Bearer {player_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "games_played" in data
        assert "avg_points" in data
        assert "avg_rebounds" in data
        assert "fg_percentage" in data

    async def test_coach_cannot_access_player_stats_endpoint(self, async_client, coach_token):
        """Test coaches cannot access /me/stats endpoint."""
        response = await async_client.get(
            "/me/stats",
            headers={"Authorization": f"Bearer {coach_token}"}
        )

        assert response.status_code == 403


@pytest.mark.integration
@pytest.mark.asyncio
class TestPlayerTeams:
    """Test /me/teams endpoint for players."""

    async def test_player_get_teams(self, async_client, player_token, player_on_team, test_team):
        """Test player can get teams they're on."""
        response = await async_client.get(
            "/me/teams",
            headers={"Authorization": f"Bearer {player_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert any(team["id"] == test_team["id"] for team in data)

    async def test_player_only_sees_own_teams(self, async_client, player_token, player_2_token, test_team, player_on_team):
        """Test players only see teams they're on."""
        # Player 2 is not on the team

        response2 = await async_client.get(
            "/me/teams",
            headers={"Authorization": f"Bearer {player_2_token}"}
        )

        teams2 = response2.json()
        assert not any(team["id"] == test_team["id"] for team in teams2)

    async def test_coach_cannot_access_player_teams_endpoint(self, async_client, coach_token):
        """Test coaches cannot access /me/teams endpoint."""
        response = await async_client.get(
            "/me/teams",
            headers={"Authorization": f"Bearer {coach_token}"}
        )

        assert response.status_code == 403
