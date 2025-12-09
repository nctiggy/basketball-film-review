"""
Security tests for input validation.

Tests SQL injection, XSS, and other input validation vulnerabilities.
"""

import pytest


@pytest.mark.security
@pytest.mark.asyncio
class TestSQLInjection:
    """Test protection against SQL injection attacks."""

    async def test_sql_injection_in_login(self, async_client):
        """Test SQL injection attempt in login username."""
        response = await async_client.post("/auth/login", json={
            "username": "admin' OR '1'='1",
            "password": "password"
        })

        # Should fail authentication, not cause SQL error
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data

    async def test_sql_injection_in_team_search(self, async_client, coach_token, test_team):
        """Test SQL injection attempt in team ID parameter."""
        # Try SQL injection in URL parameter
        malicious_id = "1' OR '1'='1"

        response = await async_client.get(
            f"/teams/{malicious_id}",
            headers={"Authorization": f"Bearer {coach_token}"}
        )

        # Should return 400 (invalid UUID) or 404, not SQL error
        assert response.status_code in [400, 404, 422]

    async def test_sql_injection_in_clip_assignment(self, async_client, coach_token, test_clip):
        """Test SQL injection attempt in assignment message."""
        response = await async_client.post(
            f"/clips/{test_clip['id']}/assign",
            headers={"Authorization": f"Bearer {coach_token}"},
            json={
                "player_ids": ["'; DROP TABLE users; --"],
                "message": "'; DELETE FROM clips; --"
            }
        )

        # Should fail validation or simply store as text
        # Important: parameterized queries prevent SQL injection
        assert response.status_code in [400, 422]


@pytest.mark.security
@pytest.mark.asyncio
class TestXSSPrevention:
    """Test protection against XSS attacks."""

    async def test_xss_in_display_name(self, async_client, player_token):
        """Test XSS attempt in display name."""
        response = await async_client.put(
            "/auth/me",
            headers={"Authorization": f"Bearer {player_token}"},
            json={
                "display_name": "<script>alert('XSS')</script>"
            }
        )

        # Should accept the input (stored as-is)
        # XSS prevention happens during output rendering, not input
        assert response.status_code == 200
        data = response.json()
        # Verify it's stored but will be escaped on output
        assert "<script>" in data["display_name"]

    async def test_xss_in_team_name(self, async_client, coach_token):
        """Test XSS attempt in team name."""
        response = await async_client.post(
            "/teams",
            headers={"Authorization": f"Bearer {coach_token}"},
            json={
                "name": "<img src=x onerror=alert('XSS')>",
                "season": "2024"
            }
        )

        # Should accept input (output escaping prevents XSS)
        assert response.status_code == 201

    async def test_xss_in_assignment_message(self, async_client, coach_token, test_clip, test_player, player_on_team):
        """Test XSS attempt in assignment message."""
        response = await async_client.post(
            f"/clips/{test_clip['id']}/assign",
            headers={"Authorization": f"Bearer {coach_token}"},
            json={
                "player_ids": [test_player["id"]],
                "message": "<script>document.location='http://evil.com'</script>"
            }
        )

        # Should accept input
        assert response.status_code == 201


@pytest.mark.security
@pytest.mark.asyncio
class TestInvalidUUIDs:
    """Test handling of invalid UUID formats."""

    async def test_invalid_uuid_in_team_access(self, async_client, coach_token):
        """Test invalid UUID format in team ID."""
        response = await async_client.get(
            "/teams/not-a-uuid",
            headers={"Authorization": f"Bearer {coach_token}"}
        )

        # Should return 400 or 422 (validation error), not crash
        assert response.status_code in [400, 422, 404]

    async def test_invalid_uuid_in_clip_assignment(self, async_client, coach_token, test_clip):
        """Test invalid UUID format in player ID."""
        response = await async_client.post(
            f"/clips/{test_clip['id']}/assign",
            headers={"Authorization": f"Bearer {coach_token}"},
            json={
                "player_ids": ["not-a-uuid", "also-not-uuid"],
                "message": "Test"
            }
        )

        # Should return validation error
        assert response.status_code in [400, 422]

    async def test_malformed_uuid_handled_gracefully(self, async_client, player_token):
        """Test that malformed UUIDs don't cause server errors."""
        malformed_ids = [
            "123",
            "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
            "00000000-0000-0000-0000-00000000000g",  # Invalid hex character
            "",
            "null"
        ]

        for malformed_id in malformed_ids:
            response = await async_client.get(
                f"/me/clips/{malformed_id}/viewed",
                headers={"Authorization": f"Bearer {player_token}"}
            )

            # Should not return 500 (server error)
            assert response.status_code != 500


@pytest.mark.security
@pytest.mark.asyncio
class TestInputLengthLimits:
    """Test handling of excessively long inputs."""

    async def test_very_long_username(self, async_client, test_invite):
        """Test registration with very long username."""
        response = await async_client.post("/auth/register", json={
            "invite_code": test_invite["code"],
            "username": "a" * 1000,  # Very long username
            "password": "password123",
            "display_name": "Test User"
        })

        # Should either accept it (DB will enforce limit) or reject with validation
        assert response.status_code in [200, 400, 422]

    async def test_very_long_message(self, async_client, coach_token, test_clip, test_player, player_on_team):
        """Test assignment with very long message."""
        response = await async_client.post(
            f"/clips/{test_clip['id']}/assign",
            headers={"Authorization": f"Bearer {coach_token}"},
            json={
                "player_ids": [test_player["id"]],
                "message": "a" * 10000  # Very long message
            }
        )

        # Should handle gracefully
        assert response.status_code in [201, 400, 422]


@pytest.mark.security
@pytest.mark.asyncio
class TestSpecialCharacters:
    """Test handling of special characters and edge cases."""

    async def test_unicode_in_display_name(self, async_client, player_token):
        """Test unicode characters in display name."""
        response = await async_client.put(
            "/auth/me",
            headers={"Authorization": f"Bearer {player_token}"},
            json={
                "display_name": "用户名 🏀 Пользователь 日本語"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "用户名" in data["display_name"]

    async def test_null_bytes_in_input(self, async_client):
        """Test null bytes in input are handled."""
        response = await async_client.post("/auth/login", json={
            "username": "test\x00user",
            "password": "password"
        })

        # Should not crash, will fail authentication
        assert response.status_code in [401, 400, 422]

    async def test_special_characters_in_team_name(self, async_client, coach_token):
        """Test special characters in team name."""
        response = await async_client.post(
            "/teams",
            headers={"Authorization": f"Bearer {coach_token}"},
            json={
                "name": "Team !@#$%^&*()_+-=[]{}|;':\",./<>?",
                "season": "2024"
            }
        )

        # Should accept special characters
        assert response.status_code == 201

    async def test_newlines_in_message(self, async_client, coach_token, test_clip, test_player, player_on_team):
        """Test newlines in assignment message."""
        response = await async_client.post(
            f"/clips/{test_clip['id']}/assign",
            headers={"Authorization": f"Bearer {coach_token}"},
            json={
                "player_ids": [test_player["id"]],
                "message": "Line 1\nLine 2\r\nLine 3"
            }
        )

        assert response.status_code == 201


@pytest.mark.security
@pytest.mark.asyncio
class TestRateLimiting:
    """Test rate limiting (if implemented)."""

    async def test_multiple_rapid_login_attempts(self, async_client, test_coach):
        """Test multiple rapid login attempts."""
        # Make multiple login attempts rapidly
        for i in range(10):
            response = await async_client.post("/auth/login", json={
                "username": test_coach["username"],
                "password": "wrong_password"
            })

        # Last response should either succeed or show rate limit
        # Note: Rate limiting not implemented yet, so this just ensures no crash
        assert response.status_code in [401, 429]  # 429 = Too Many Requests

    @pytest.mark.skip(reason="Rate limiting not yet implemented")
    async def test_rate_limit_on_api_endpoints(self, async_client, coach_token):
        """Test rate limiting on API endpoints."""
        # Make many rapid requests
        responses = []
        for i in range(150):  # Over the limit
            response = await async_client.get(
                "/teams",
                headers={"Authorization": f"Bearer {coach_token}"}
            )
            responses.append(response.status_code)

        # Should eventually get 429 (Too Many Requests)
        assert 429 in responses
