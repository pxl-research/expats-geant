"""Unit tests for JWT authentication."""

import logging
import os
from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from m_shared.auth.jwt_handler import (
    TokenExpiredError,
    TokenInvalidError,
    create_token,
    validate_token,
    verify_session_access,
)


class TestCreateToken:
    """Test JWT token creation."""

    def test_create_token_basic(self):
        """Test creating a token with basic parameters."""
        with patch.dict(os.environ, {"JWT_SECRET": "test-secret-key"}):
            token = create_token("user123", "session456")
            assert isinstance(token, str)
            assert len(token) > 0

    def test_create_token_with_roles(self):
        """Test creating a token with custom roles."""
        with patch.dict(os.environ, {"JWT_SECRET": "test-secret-key"}):
            token = create_token("user123", "session456", roles=["administrator", "respondent"])
            claims = validate_token(token)
            assert claims["roles"] == ["administrator", "respondent"]

    def test_create_token_with_org(self):
        """Test creating a token with organization."""
        with patch.dict(os.environ, {"JWT_SECRET": "test-secret-key"}):
            token = create_token("user123", "session456", org="pxl-university")
            claims = validate_token(token)
            assert claims["org"] == "pxl-university"

    def test_create_token_default_roles(self):
        """Test that respondent role is default."""
        with patch.dict(os.environ, {"JWT_SECRET": "test-secret-key"}):
            token = create_token("user123", "session456")
            claims = validate_token(token)
            assert claims["roles"] == ["respondent"]

    def test_create_token_custom_expiration(self):
        """Test creating a token with custom expiration."""
        with patch.dict(os.environ, {"JWT_SECRET": "test-secret-key"}):
            token = create_token("user123", "session456", expiration_hours=48)
            claims = validate_token(token)

            # Check expiration is approximately 48 hours from now
            exp_time = datetime.fromtimestamp(claims["exp"], tz=UTC)
            now = datetime.now(UTC)
            diff = (exp_time - now).total_seconds() / 3600
            assert 47.9 < diff < 48.1  # Allow small timing variations

    def test_create_token_env_expiration(self):
        """Test expiration from environment variable."""
        with patch.dict(
            os.environ, {"JWT_SECRET": "test-secret-key", "JWT_EXPIRATION_HOURS": "12"}
        ):
            token = create_token("user123", "session456")
            claims = validate_token(token)

            exp_time = datetime.fromtimestamp(claims["exp"], tz=UTC)
            now = datetime.now(UTC)
            diff = (exp_time - now).total_seconds() / 3600
            assert 11.9 < diff < 12.1

    def test_create_token_missing_secret(self):
        """Test that missing JWT_SECRET raises ValueError."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="JWT_SECRET"):
                create_token("user123", "session456")

    def test_create_token_custom_algorithm(self):
        """Test using custom algorithm from environment."""
        with patch.dict(os.environ, {"JWT_SECRET": "test-secret-key", "JWT_ALGORITHM": "HS512"}):
            token = create_token("user123", "session456")
            # Should still be decodable with HS512
            claims = validate_token(token)
            assert claims["user_id"] == "user123"


class TestValidateToken:
    """Test JWT token validation."""

    def test_validate_token_success(self):
        """Test validating a valid token."""
        with patch.dict(os.environ, {"JWT_SECRET": "test-secret-key"}):
            token = create_token("user123", "session456", org="testorg")
            claims = validate_token(token)

            assert claims["user_id"] == "user123"
            assert claims["session_id"] == "session456"
            assert claims["org"] == "testorg"
            assert "iat" in claims
            assert "exp" in claims

    def test_validate_token_expired(self):
        """Test that expired tokens raise TokenExpiredError."""
        with patch.dict(os.environ, {"JWT_SECRET": "test-secret-key"}):
            # Create a token that expires immediately
            token = create_token("user123", "session456", expiration_hours=-1)

            with pytest.raises(TokenExpiredError, match="expired"):
                validate_token(token)

    def test_validate_token_invalid_signature(self):
        """Test that tokens with invalid signatures raise TokenInvalidError."""
        with patch.dict(os.environ, {"JWT_SECRET": "test-secret-key"}):
            token = create_token("user123", "session456")

        # Change the secret and try to validate
        with patch.dict(os.environ, {"JWT_SECRET": "different-secret"}):
            with pytest.raises(TokenInvalidError, match="Invalid token"):
                validate_token(token)

    def test_validate_token_malformed(self):
        """Test that malformed tokens raise TokenInvalidError."""
        with patch.dict(os.environ, {"JWT_SECRET": "test-secret-key"}):
            with pytest.raises(TokenInvalidError):
                validate_token("not.a.valid.jwt.token")

    def test_validate_token_missing_secret(self):
        """Test that missing JWT_SECRET raises ValueError."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="JWT_SECRET"):
                validate_token("some.token.here")

    def test_validate_token_algorithm_mismatch(self):
        """Test validation with algorithm mismatch."""
        with patch.dict(os.environ, {"JWT_SECRET": "test-secret-key", "JWT_ALGORITHM": "HS256"}):
            token = create_token("user123", "session456")

        # Try to validate with different algorithm
        with patch.dict(os.environ, {"JWT_SECRET": "test-secret-key", "JWT_ALGORITHM": "HS512"}):
            with pytest.raises(TokenInvalidError):
                validate_token(token)


class TestVerifySessionAccess:
    """Test session isolation enforcement."""

    def test_verify_session_access_allowed(self):
        """Test that access to own session is allowed."""
        with patch.dict(os.environ, {"JWT_SECRET": "test-secret-key"}):
            token = create_token("user123", "session456")
            claims = validate_token(token)

            # Should return True for matching session
            assert verify_session_access(claims, "session456") is True

    def test_verify_session_access_denied(self):
        """Test that access to other sessions is denied."""
        with patch.dict(os.environ, {"JWT_SECRET": "test-secret-key"}):
            token = create_token("user123", "session456")
            claims = validate_token(token)

            # Should raise PermissionError for different session
            with pytest.raises(PermissionError, match="Access denied"):
                verify_session_access(claims, "session789")

    def test_verify_session_access_missing_claim(self):
        """Test behavior when session_id claim is missing."""
        claims = {"user_id": "user123", "org": "test"}

        with pytest.raises(PermissionError):
            verify_session_access(claims, "session456")


class TestTokenRoundTrip:
    """Test complete token lifecycle."""

    def test_full_auth_flow(self):
        """Test complete authentication flow."""
        with patch.dict(os.environ, {"JWT_SECRET": "test-secret-key"}):
            # 1. User logs in, token created
            token = create_token(
                user_id="user123",
                session_id="session456",
                org="pxl-university",
                roles=["respondent"],
            )

            # 2. User makes request, token validated
            claims = validate_token(token)
            assert claims["user_id"] == "user123"
            assert claims["session_id"] == "session456"

            # 3. User accesses their own session - allowed
            assert verify_session_access(claims, "session456") is True

            # 4. User tries to access another session - denied
            with pytest.raises(PermissionError):
                verify_session_access(claims, "other-session")

    def test_administrator_vs_respondent_roles(self):
        """Test different role configurations."""
        with patch.dict(os.environ, {"JWT_SECRET": "test-secret-key"}):
            # Respondent token
            respondent_token = create_token("user1", "session1", roles=["respondent"])
            respondent_claims = validate_token(respondent_token)
            assert respondent_claims["roles"] == ["respondent"]

            # Administrator token
            admin_token = create_token("admin1", "session2", roles=["administrator"])
            admin_claims = validate_token(admin_token)
            assert admin_claims["roles"] == ["administrator"]


class TestSecurityEventLogging:
    """Verify security events are logged at the correct level."""

    def test_expired_token_logs_warning(self, caplog):
        """Expired token validation must emit a WARNING."""
        with patch.dict(os.environ, {"JWT_SECRET": "test-secret-key"}):
            token = create_token("user123", "session456", expiration_hours=-1)
            with caplog.at_level(logging.WARNING, logger="m_shared.auth.jwt_handler"):
                with pytest.raises(TokenExpiredError):
                    validate_token(token)
        assert any("expired" in r.message.lower() for r in caplog.records)
        assert all(r.levelno <= logging.WARNING for r in caplog.records)

    def test_invalid_token_logs_warning(self, caplog):
        """Invalid token validation must emit a WARNING."""
        with patch.dict(os.environ, {"JWT_SECRET": "test-secret-key"}):
            with caplog.at_level(logging.WARNING, logger="m_shared.auth.jwt_handler"):
                with pytest.raises(TokenInvalidError):
                    validate_token("not.a.valid.jwt")
        assert any("validation failed" in r.message.lower() for r in caplog.records)

    def test_missing_secret_on_creation_logs_error(self, caplog):
        """Missing JWT_SECRET on token creation must emit an ERROR."""
        with patch.dict(os.environ, {}, clear=True):
            with caplog.at_level(logging.ERROR, logger="m_shared.auth.jwt_handler"):
                with pytest.raises(ValueError):
                    create_token("user123", "session456")
        assert any(r.levelno == logging.ERROR for r in caplog.records)
        assert any("token creation failed" in r.message.lower() for r in caplog.records)
