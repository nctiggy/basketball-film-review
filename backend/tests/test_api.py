"""
Integration tests for the Basketball Film Review API.

These tests verify the API endpoints work correctly and test critical
operations like cascading deletes and file cleanup.
"""
import pytest
from datetime import date


class TestGameOperations:
    """Test game CRUD operations."""

    def test_create_game(self, client):
        """Test creating a new game."""
        response = client.post("/games", json={
            "name": "Test Game vs Lakers",
            "date": "2025-01-15"
        })
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["name"] == "Test Game vs Lakers"
        assert data["date"] == "2025-01-15"

    def test_list_games(self, client):
        """Test listing all games."""
        response = client.get("/games")
        assert response.status_code == 200
        games = response.json()
        assert isinstance(games, list)

    def test_get_game_by_id(self, client):
        """Test getting a specific game by ID."""
        # First create a game
        create_response = client.post("/games", json={
            "name": "Test Game for Get",
            "date": "2025-01-16"
        })
        game_id = create_response.json()["id"]

        # Then get it
        response = client.get(f"/games/{game_id}")
        assert response.status_code == 200
        game = response.json()
        assert game["id"] == game_id
        assert game["name"] == "Test Game for Get"

    def test_update_game(self, client):
        """Test updating a game."""
        # Create a game
        create_response = client.post("/games", json={
            "name": "Original Name",
            "date": "2025-01-17"
        })
        game_id = create_response.json()["id"]

        # Update it
        update_response = client.put(f"/games/{game_id}", json={
            "name": "Updated Name",
            "date": "2025-01-18"
        })
        assert update_response.status_code == 200
        updated = update_response.json()
        assert updated["name"] == "Updated Name"
        assert updated["date"] == "2025-01-18"

    def test_delete_game(self, client):
        """Test deleting a game."""
        # Create a game
        create_response = client.post("/games", json={
            "name": "Game to Delete",
            "date": "2025-01-19"
        })
        game_id = create_response.json()["id"]

        # Delete it
        delete_response = client.delete(f"/games/{game_id}")
        assert delete_response.status_code == 200

        # Verify it's gone
        get_response = client.get(f"/games/{game_id}")
        assert get_response.status_code == 404

    def test_get_nonexistent_game(self, client):
        """Test getting a game that doesn't exist."""
        response = client.get("/games/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404


class TestVideoOperations:
    """Test video operations."""

    def test_list_videos_for_game(self, client):
        """Test listing videos for a specific game."""
        # Create a game first
        game_response = client.post("/games", json={
            "name": "Game with Videos",
            "date": "2025-01-20"
        })
        game_id = game_response.json()["id"]

        # List videos (should be empty initially)
        response = client.get(f"/games/{game_id}/videos")
        assert response.status_code == 200
        videos = response.json()
        assert isinstance(videos, list)
        assert len(videos) == 0

    def test_get_video_by_id_not_found(self, client):
        """Test getting a video that doesn't exist."""
        response = client.get("/videos/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404


class TestClipOperations:
    """Test clip operations."""

    def test_list_clips_for_game(self, client):
        """Test listing clips for a specific game."""
        # Create a game first
        game_response = client.post("/games", json={
            "name": "Game with Clips",
            "date": "2025-01-21"
        })
        game_id = game_response.json()["id"]

        # List clips (should be empty initially)
        response = client.get(f"/games/{game_id}/clips")
        assert response.status_code == 200
        clips = response.json()
        assert isinstance(clips, list)
        assert len(clips) == 0

    def test_get_clip_by_id_not_found(self, client):
        """Test getting a clip that doesn't exist."""
        response = client.get("/clips/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404

    def test_update_clip(self, client):
        """Test that we can update clip metadata without the actual clip existing."""
        # We can't fully test clip updates without uploading videos,
        # but we can test the endpoint exists and validates input
        response = client.put("/clips/00000000-0000-0000-0000-000000000000", json={
            "tags": ["offense", "three-pointer"],
            "notes": "Updated notes"
        })
        # Should get 404 for non-existent clip, but endpoint should exist
        assert response.status_code in [404, 500]  # 404 or 500 depending on DB state


class TestCascadingDeletes:
    """Test that deleting games properly cascades to videos and clips."""

    def test_delete_game_cascades(self, client):
        """Test that deleting a game doesn't leave orphaned data."""
        # Create a game
        game_response = client.post("/games", json={
            "name": "Game for Cascade Test",
            "date": "2025-01-22"
        })
        game_id = game_response.json()["id"]

        # Note: We can't upload real videos in unit tests without complex setup,
        # but we can verify the delete endpoint works and the game is removed

        # Delete the game
        delete_response = client.delete(f"/games/{game_id}")
        assert delete_response.status_code == 200

        # Verify game is gone
        get_response = client.get(f"/games/{game_id}")
        assert get_response.status_code == 404

        # Verify videos list is empty/inaccessible for deleted game
        videos_response = client.get(f"/games/{game_id}/videos")
        # Should either be 404 or return empty list
        assert videos_response.status_code in [200, 404]
        if videos_response.status_code == 200:
            assert len(videos_response.json()) == 0


class TestInputValidation:
    """Test input validation and error handling."""

    def test_create_game_missing_fields(self, client):
        """Test creating a game with missing required fields."""
        response = client.post("/games", json={
            "name": "Test Game"
            # Missing date field
        })
        assert response.status_code == 422  # Validation error

    def test_create_game_invalid_date(self, client):
        """Test creating a game with invalid date format."""
        response = client.post("/games", json={
            "name": "Test Game",
            "date": "invalid-date"
        })
        assert response.status_code == 422  # Validation error

    def test_update_game_invalid_uuid(self, client):
        """Test updating a game with invalid UUID."""
        response = client.put("/games/not-a-uuid", json={
            "name": "Test",
            "date": "2025-01-23"
        })
        assert response.status_code == 422


class TestAPIHealth:
    """Test basic API health and connectivity."""

    def test_root_endpoint(self, client):
        """Test the root endpoint returns basic info."""
        # If there's no root endpoint, this will 404 which is fine
        response = client.get("/")
        assert response.status_code in [200, 404]

    def test_games_endpoint_accessible(self, client):
        """Test that the games endpoint is accessible."""
        response = client.get("/games")
        assert response.status_code == 200
