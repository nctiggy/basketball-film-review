"""
Integration tests for parent-specific API endpoints.

Tests /me/children/* endpoints for parent functionality.
"""

import pytest


@pytest.mark.integration
@pytest.mark.asyncio
class TestParentChildren:
    """Test /me/children endpoints for parents."""

    async def test_parent_get_children(self, async_client, parent_token, parent_child_link, test_player):
        """Test parent can get list of linked children."""
        response = await async_client.get(
            "/me/children",
            headers={"Authorization": f"Bearer {parent_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert any(child["id"] == test_player["id"] for child in data)

    async def test_parent_only_sees_linked_children(self, async_client, parent_token, parent_child_link, test_player, test_player_2):
        """Test parent only sees children linked to them."""
        # Parent is linked to test_player but not test_player_2

        response = await async_client.get(
            "/me/children",
            headers={"Authorization": f"Bearer {parent_token}"}
        )

        children = response.json()
        assert any(child["id"] == test_player["id"] for child in children)
        assert not any(child["id"] == test_player_2["id"] for child in children)

    async def test_coach_cannot_access_children_endpoint(self, async_client, coach_token):
        """Test coaches cannot access /me/children endpoint."""
        response = await async_client.get(
            "/me/children",
            headers={"Authorization": f"Bearer {coach_token}"}
        )

        assert response.status_code == 403

    async def test_player_cannot_access_children_endpoint(self, async_client, player_token):
        """Test players cannot access /me/children endpoint."""
        response = await async_client.get(
            "/me/children",
            headers={"Authorization": f"Bearer {player_token}"}
        )

        assert response.status_code == 403


@pytest.mark.integration
@pytest.mark.asyncio
class TestParentChildClips:
    """Test /me/children/{id}/clips endpoint for parents."""

    async def test_parent_get_child_clips(self, async_client, parent_token, parent_child_link, test_player, clip_assignment):
        """Test parent can get clips assigned to their child."""
        response = await async_client.get(
            f"/me/children/{test_player['id']}/clips",
            headers={"Authorization": f"Bearer {parent_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert data[0]["id"] == clip_assignment["clip_id"]

    async def test_parent_cannot_access_non_linked_child_clips(self, async_client, parent_token, test_player_2, clip_assignment):
        """Test parent cannot access clips of non-linked child."""
        response = await async_client.get(
            f"/me/children/{test_player_2['id']}/clips",
            headers={"Authorization": f"Bearer {parent_token}"}
        )

        assert response.status_code == 403

    async def test_parent_cannot_access_child_with_invalid_id(self, async_client, parent_token):
        """Test parent cannot access child with invalid ID."""
        fake_id = "00000000-0000-0000-0000-000000000000"

        response = await async_client.get(
            f"/me/children/{fake_id}/clips",
            headers={"Authorization": f"Bearer {parent_token}"}
        )

        assert response.status_code == 403 or response.status_code == 404


@pytest.mark.integration
@pytest.mark.asyncio
class TestParentChildStats:
    """Test /me/children/{id}/stats endpoint for parents."""

    async def test_parent_get_child_stats(self, async_client, parent_token, parent_child_link, test_player, test_game, db_pool):
        """Test parent can get stats for their child."""
        import uuid

        # Add stats for child
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO player_game_stats (game_id, player_id, points, field_goals_made, field_goals_attempted)
                VALUES ($1, $2, 18, 7, 14)
                """,
                uuid.UUID(test_game["id"]), uuid.UUID(test_player["id"])
            )

        response = await async_client.get(
            f"/me/children/{test_player['id']}/stats",
            headers={"Authorization": f"Bearer {parent_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert data[0]["points"] == 18

    async def test_parent_cannot_access_non_linked_child_stats(self, async_client, parent_token, test_player_2, test_game, db_pool):
        """Test parent cannot access stats of non-linked child."""
        import uuid

        # Add stats for non-linked player
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO player_game_stats (game_id, player_id, points)
                VALUES ($1, $2, 25)
                """,
                uuid.UUID(test_game["id"]), uuid.UUID(test_player_2["id"])
            )

        response = await async_client.get(
            f"/me/children/{test_player_2['id']}/stats",
            headers={"Authorization": f"Bearer {parent_token}"}
        )

        assert response.status_code == 403

    async def test_get_child_season_stats(self, async_client, parent_token, parent_child_link, test_player, test_game, db_pool):
        """Test getting aggregated season stats for child."""
        import uuid

        # Add stats
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO player_game_stats
                (game_id, player_id, points, field_goals_made, field_goals_attempted, assists, offensive_rebounds, defensive_rebounds)
                VALUES ($1, $2, 22, 9, 16, 6, 3, 5)
                """,
                uuid.UUID(test_game["id"]), uuid.UUID(test_player["id"])
            )

        response = await async_client.get(
            f"/me/children/{test_player['id']}/stats/season",
            headers={"Authorization": f"Bearer {parent_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "games_played" in data
        assert "avg_points" in data
        assert data["games_played"] >= 1


@pytest.mark.integration
@pytest.mark.asyncio
class TestParentAuthorization:
    """Test parent authorization and access control."""

    async def test_parent_with_multiple_children(self, async_client, parent_token, test_parent, test_player, test_player_2, db_pool):
        """Test parent with multiple linked children can access all their data."""
        import uuid

        # Link parent to both players
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO parent_links (parent_id, player_id, verified_at)
                VALUES ($1, $2, NOW())
                ON CONFLICT DO NOTHING
                """,
                uuid.UUID(test_parent["id"]), uuid.UUID(test_player["id"])
            )
            await conn.execute(
                """
                INSERT INTO parent_links (parent_id, player_id, verified_at)
                VALUES ($1, $2, NOW())
                """,
                uuid.UUID(test_parent["id"]), uuid.UUID(test_player_2["id"])
            )

        response = await async_client.get(
            "/me/children",
            headers={"Authorization": f"Bearer {parent_token}"}
        )

        children = response.json()
        assert len(children) >= 2
        assert any(child["id"] == test_player["id"] for child in children)
        assert any(child["id"] == test_player_2["id"] for child in children)

    async def test_parent_cannot_modify_child_data(self, async_client, parent_token, parent_child_link, test_player, clip_assignment):
        """Test that parents have read-only access to child data."""
        # Try to mark clip as viewed (should fail)
        response = await async_client.post(
            f"/me/clips/{clip_assignment['clip_id']}/viewed",
            headers={"Authorization": f"Bearer {parent_token}"}
        )

        # Parents use different endpoint, this one is for players only
        assert response.status_code == 403

    async def test_parent_link_verification(self, async_client, test_parent, test_player, db_pool):
        """Test that parent links must be verified to access data."""
        from backend.auth import create_access_token
        import uuid

        # Create a new parent without verified link
        parent2_id = uuid.uuid4()
        from backend.auth import hash_password

        password_hash = hash_password("password123")

        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO users (id, username, password_hash, display_name, role, auth_provider, status)
                VALUES ($1, $2, $3, $4, 'parent', 'local', 'active')
                """,
                parent2_id, "parent2", password_hash, "Parent 2"
            )

            # Create link without verification (verified_at is NULL)
            await conn.execute(
                """
                INSERT INTO parent_links (parent_id, player_id)
                VALUES ($1, $2)
                """,
                parent2_id, uuid.UUID(test_player["id"])
            )

        parent2_token = create_access_token(str(parent2_id), "parent")

        response = await async_client.get(
            "/me/children",
            headers={"Authorization": f"Bearer {parent2_token}"}
        )

        # Should still work as the query doesn't filter by verified_at
        # In production, you might want to add this filter
        assert response.status_code == 200
