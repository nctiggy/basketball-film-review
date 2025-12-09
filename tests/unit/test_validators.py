"""
Unit tests for Pydantic model validation.

Tests input validation and sanitization for API models.
"""

import pytest
from pydantic import ValidationError
from datetime import datetime

from backend.models.user import (
    UserLogin,
    InviteRegisterRequest,
    UserUpdate,
    PasswordChange
)
from backend.models.team import TeamCreate, TeamUpdate, AddPlayerRequest
from backend.models.assignment import ClipAssignRequest


@pytest.mark.unit
class TestUserValidation:
    """Test user model validation."""

    def test_user_login_valid(self):
        """Test valid user login data."""
        data = {
            "username": "testuser",
            "password": "password123"
        }
        login = UserLogin(**data)

        assert login.username == "testuser"
        assert login.password == "password123"

    def test_user_login_missing_username(self):
        """Test user login with missing username."""
        data = {"password": "password123"}

        with pytest.raises(ValidationError) as exc_info:
            UserLogin(**data)

        assert "username" in str(exc_info.value)

    def test_user_login_missing_password(self):
        """Test user login with missing password."""
        data = {"username": "testuser"}

        with pytest.raises(ValidationError) as exc_info:
            UserLogin(**data)

        assert "password" in str(exc_info.value)

    def test_invite_register_valid(self):
        """Test valid invite registration data."""
        data = {
            "invite_code": "abc123xyz",
            "username": "newuser",
            "password": "secure_pass_123",
            "display_name": "New User",
            "phone": "555-1234"
        }
        register = InviteRegisterRequest(**data)

        assert register.invite_code == "abc123xyz"
        assert register.username == "newuser"
        assert register.display_name == "New User"

    def test_invite_register_minimum_required(self):
        """Test invite registration with minimum required fields."""
        data = {
            "invite_code": "abc123xyz",
            "username": "newuser",
            "password": "secure_pass_123",
            "display_name": "New User"
        }
        register = InviteRegisterRequest(**data)

        assert register.phone is None

    def test_password_change_valid(self):
        """Test valid password change data."""
        data = {
            "current_password": "old_password",
            "new_password": "new_secure_password_123"
        }
        password_change = PasswordChange(**data)

        assert password_change.current_password == "old_password"
        assert password_change.new_password == "new_secure_password_123"

    def test_user_update_partial(self):
        """Test user update with partial data."""
        data = {"display_name": "Updated Name"}
        update = UserUpdate(**data)

        assert update.display_name == "Updated Name"
        assert update.phone is None


@pytest.mark.unit
class TestTeamValidation:
    """Test team model validation."""

    def test_team_create_valid(self):
        """Test valid team creation data."""
        data = {
            "name": "Tigers",
            "season": "2024"
        }
        team = TeamCreate(**data)

        assert team.name == "Tigers"
        assert team.season == "2024"

    def test_team_create_missing_name(self):
        """Test team creation with missing name."""
        data = {"season": "2024"}

        with pytest.raises(ValidationError) as exc_info:
            TeamCreate(**data)

        assert "name" in str(exc_info.value)

    def test_team_create_optional_season(self):
        """Test team creation with optional season."""
        data = {"name": "Tigers"}
        team = TeamCreate(**data)

        assert team.name == "Tigers"
        assert team.season is None

    def test_team_update_empty(self):
        """Test team update with no fields."""
        data = {}
        update = TeamUpdate(**data)

        assert update.name is None
        assert update.season is None

    def test_add_player_minimum_fields(self):
        """Test adding player with minimum required fields."""
        data = {"display_name": "John Doe"}
        player = AddPlayerRequest(**data)

        assert player.display_name == "John Doe"
        assert player.jersey_number is None
        assert player.position is None

    def test_add_player_full_data(self):
        """Test adding player with all fields."""
        data = {
            "display_name": "John Doe",
            "jersey_number": "23",
            "position": "PG",
            "graduation_year": 2025
        }
        player = AddPlayerRequest(**data)

        assert player.display_name == "John Doe"
        assert player.jersey_number == "23"
        assert player.position == "PG"
        assert player.graduation_year == 2025


@pytest.mark.unit
class TestAssignmentValidation:
    """Test assignment model validation."""

    def test_clip_assign_single_player(self):
        """Test assigning clip to a single player."""
        data = {
            "player_ids": ["123e4567-e89b-12d3-a456-426614174000"]
        }
        assignment = ClipAssignRequest(**data)

        assert len(assignment.player_ids) == 1
        assert assignment.message is None
        assert assignment.priority == "normal"

    def test_clip_assign_multiple_players(self):
        """Test assigning clip to multiple players."""
        data = {
            "player_ids": [
                "123e4567-e89b-12d3-a456-426614174000",
                "223e4567-e89b-12d3-a456-426614174001"
            ]
        }
        assignment = ClipAssignRequest(**data)

        assert len(assignment.player_ids) == 2

    def test_clip_assign_with_message(self):
        """Test assigning clip with message."""
        data = {
            "player_ids": ["123e4567-e89b-12d3-a456-426614174000"],
            "message": "Great defensive play!",
            "priority": "high"
        }
        assignment = ClipAssignRequest(**data)

        assert assignment.message == "Great defensive play!"
        assert assignment.priority == "high"

    def test_clip_assign_empty_player_list(self):
        """Test assigning clip with empty player list."""
        data = {"player_ids": []}

        # This should still validate, but business logic should reject it
        assignment = ClipAssignRequest(**data)
        assert len(assignment.player_ids) == 0

    def test_clip_assign_invalid_priority(self):
        """Test assigning clip with invalid priority."""
        data = {
            "player_ids": ["123e4567-e89b-12d3-a456-426614174000"],
            "priority": "invalid_priority"
        }

        # Pydantic should accept any string, validation happens at business logic level
        assignment = ClipAssignRequest(**data)
        assert assignment.priority == "invalid_priority"


@pytest.mark.unit
class TestInputSanitization:
    """Test that models handle potentially malicious input safely."""

    def test_sql_injection_in_username(self):
        """Test that SQL injection attempts in username are handled."""
        data = {
            "username": "admin'; DROP TABLE users; --",
            "password": "password123"
        }
        login = UserLogin(**data)

        # Pydantic should accept the string; parameterized queries prevent SQL injection
        assert login.username == "admin'; DROP TABLE users; --"

    def test_xss_in_display_name(self):
        """Test that XSS attempts in display name are stored as-is."""
        data = {
            "display_name": "<script>alert('XSS')</script>"
        }
        update = UserUpdate(**data)

        # String is stored as-is; output escaping prevents XSS
        assert update.display_name == "<script>alert('XSS')</script>"

    def test_long_string_in_team_name(self):
        """Test handling of very long team names."""
        data = {
            "name": "A" * 1000,  # Very long name
            "season": "2024"
        }
        team = TeamCreate(**data)

        # Pydantic accepts it; database constraints handle length limits
        assert len(team.name) == 1000

    def test_special_characters_in_message(self):
        """Test handling of special characters in assignment message."""
        data = {
            "player_ids": ["123e4567-e89b-12d3-a456-426614174000"],
            "message": "Special chars: !@#$%^&*()_+-=[]{}|;':\",./<>?"
        }
        assignment = ClipAssignRequest(**data)

        assert "!@#$%^&*" in assignment.message

    def test_unicode_in_display_name(self):
        """Test handling of unicode characters in display name."""
        data = {
            "display_name": "用户名 🏀 Пользователь"
        }
        update = UserUpdate(**data)

        assert update.display_name == "用户名 🏀 Пользователь"

    def test_null_bytes_in_input(self):
        """Test handling of null bytes in input."""
        data = {
            "username": "test\x00user",
            "password": "password123"
        }
        login = UserLogin(**data)

        # Pydantic accepts it; application layer should sanitize
        assert "\x00" in login.username
