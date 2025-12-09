"""
Unit tests for authentication utilities.

Tests JWT token creation, validation, and password hashing.
"""

import pytest
from datetime import datetime, timedelta
from jwt.exceptions import InvalidTokenError

from backend.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password
)


class TestJWTTokens:
    """Test JWT token creation and validation."""

    def test_create_access_token(self):
        """Test creating an access token."""
        user_id = "123e4567-e89b-12d3-a456-426614174000"
        role = "coach"

        token = create_access_token(user_id, role)

        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_refresh_token(self):
        """Test creating a refresh token."""
        user_id = "123e4567-e89b-12d3-a456-426614174000"

        token = create_refresh_token(user_id)

        assert isinstance(token, str)
        assert len(token) > 0

    def test_decode_access_token(self):
        """Test decoding a valid access token."""
        user_id = "123e4567-e89b-12d3-a456-426614174000"
        role = "player"

        token = create_access_token(user_id, role)
        payload = decode_token(token)

        assert payload["sub"] == user_id
        assert payload["role"] == role
        assert payload["type"] == "access"
        assert "exp" in payload
        assert "iat" in payload

    def test_decode_refresh_token(self):
        """Test decoding a valid refresh token."""
        user_id = "123e4567-e89b-12d3-a456-426614174000"

        token = create_refresh_token(user_id)
        payload = decode_token(token)

        assert payload["sub"] == user_id
        assert payload["type"] == "refresh"
        assert "exp" in payload
        assert "iat" in payload

    def test_decode_invalid_token(self):
        """Test decoding an invalid token raises error."""
        invalid_token = "invalid.token.here"

        with pytest.raises(InvalidTokenError):
            decode_token(invalid_token)

    def test_decode_tampered_token(self):
        """Test decoding a tampered token raises error."""
        user_id = "123e4567-e89b-12d3-a456-426614174000"
        role = "coach"

        token = create_access_token(user_id, role)
        # Tamper with the token
        tampered_token = token[:-5] + "xxxxx"

        with pytest.raises(InvalidTokenError):
            decode_token(tampered_token)

    def test_token_contains_expiration(self):
        """Test that tokens contain expiration timestamp."""
        user_id = "123e4567-e89b-12d3-a456-426614174000"
        role = "coach"

        token = create_access_token(user_id, role)
        payload = decode_token(token)

        # Check expiration is in the future
        exp_timestamp = payload["exp"]
        assert exp_timestamp > datetime.utcnow().timestamp()

    def test_access_token_additional_claims(self):
        """Test adding additional claims to access token."""
        user_id = "123e4567-e89b-12d3-a456-426614174000"
        role = "coach"
        additional_claims = {"custom_field": "custom_value"}

        token = create_access_token(user_id, role, additional_claims)
        payload = decode_token(token)

        assert payload["custom_field"] == "custom_value"


class TestPasswordHashing:
    """Test password hashing and verification."""

    def test_hash_password(self):
        """Test hashing a password."""
        password = "my_secure_password_123"

        hashed = hash_password(password)

        assert isinstance(hashed, str)
        assert len(hashed) > 0
        assert hashed != password  # Should be hashed, not plain text

    def test_verify_correct_password(self):
        """Test verifying a correct password."""
        password = "my_secure_password_123"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_incorrect_password(self):
        """Test verifying an incorrect password."""
        password = "my_secure_password_123"
        wrong_password = "wrong_password"
        hashed = hash_password(password)

        assert verify_password(wrong_password, hashed) is False

    def test_hash_same_password_twice_different_hashes(self):
        """Test that hashing the same password twice produces different hashes (due to salt)."""
        password = "my_secure_password_123"

        hash1 = hash_password(password)
        hash2 = hash_password(password)

        # Hashes should be different due to random salt
        assert hash1 != hash2
        # But both should verify correctly
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True

    def test_verify_empty_password(self):
        """Test verifying an empty password."""
        password = ""
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True
        assert verify_password("non-empty", hashed) is False

    def test_verify_with_invalid_hash(self):
        """Test verifying password with invalid hash format."""
        password = "my_secure_password_123"
        invalid_hash = "not_a_valid_hash"

        assert verify_password(password, invalid_hash) is False

    def test_password_case_sensitive(self):
        """Test that password verification is case-sensitive."""
        password = "MyPassword123"
        hashed = hash_password(password)

        assert verify_password("MyPassword123", hashed) is True
        assert verify_password("mypassword123", hashed) is False
        assert verify_password("MYPASSWORD123", hashed) is False

    def test_password_with_special_characters(self):
        """Test password hashing with special characters."""
        password = "P@ssw0rd!#$%^&*()"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True
        assert verify_password("P@ssw0rd!#$%^&*()x", hashed) is False

    def test_password_with_unicode(self):
        """Test password hashing with unicode characters."""
        password = "пароль密码🔒"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True
        assert verify_password("пароль密码", hashed) is False


@pytest.mark.unit
class TestTokenSecurity:
    """Test security properties of tokens."""

    def test_access_token_has_limited_lifetime(self):
        """Test that access tokens have reasonable expiration."""
        user_id = "123e4567-e89b-12d3-a456-426614174000"
        role = "coach"

        token = create_access_token(user_id, role)
        payload = decode_token(token)

        # Calculate token lifetime
        exp_time = datetime.fromtimestamp(payload["exp"])
        iat_time = datetime.fromtimestamp(payload["iat"])
        lifetime = exp_time - iat_time

        # Access tokens should expire within 48 hours (typical: 24h)
        assert lifetime <= timedelta(hours=48)

    def test_refresh_token_has_longer_lifetime(self):
        """Test that refresh tokens have longer expiration than access tokens."""
        user_id = "123e4567-e89b-12d3-a456-426614174000"

        refresh_token = create_refresh_token(user_id)
        access_token = create_access_token(user_id, "coach")

        refresh_payload = decode_token(refresh_token)
        access_payload = decode_token(access_token)

        # Refresh token should expire later than access token
        assert refresh_payload["exp"] > access_payload["exp"]

    def test_token_type_differentiation(self):
        """Test that access and refresh tokens have different types."""
        user_id = "123e4567-e89b-12d3-a456-426614174000"

        access_token = create_access_token(user_id, "coach")
        refresh_token = create_refresh_token(user_id)

        access_payload = decode_token(access_token)
        refresh_payload = decode_token(refresh_token)

        assert access_payload["type"] == "access"
        assert refresh_payload["type"] == "refresh"
        assert access_payload["type"] != refresh_payload["type"]
