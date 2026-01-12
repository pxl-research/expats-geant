"""Tests for session middleware and API endpoints."""

import os
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from m_shared.auth.jwt_handler import create_token
from m_shared.auth.middleware import SessionMiddleware
from m_shared.session.manager import SessionManager
from m_autofill.api import create_app


@pytest.fixture
def jwt_secret(monkeypatch):
    """Set JWT secret for testing."""
    monkeypatch.setenv("JWT_SECRET", "test-secret-key")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("JWT_EXPIRATION_HOURS", "24")
    return "test-secret-key"


@pytest.fixture
def session_manager(tmp_path):
    """Create session manager with temporary storage."""
    return SessionManager(base_path=str(tmp_path / "sessions"))


@pytest.fixture
def app(session_manager):
    """Create FastAPI app with session middleware."""
    app = create_app(session_manager)
    app.add_middleware(SessionMiddleware, session_manager=session_manager, ttl_hours=24)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def valid_token(jwt_secret):
    """Create valid JWT token."""
    return create_token(
        user_id="test_user_123",
        session_id="test_session_456",
        org="test_org",
        roles=["respondent"]
    )


@pytest.fixture
def expired_token(jwt_secret, monkeypatch):
    """Create expired JWT token."""
    # Create token that expired 1 hour ago
    monkeypatch.setenv("JWT_EXPIRATION_HOURS", "0")
    token = create_token(
        user_id="test_user_123",
        session_id="test_session_456",
        org="test_org",
        roles=["respondent"]
    )
    # Reset expiration hours
    monkeypatch.setenv("JWT_EXPIRATION_HOURS", "24")
    return token


class TestSessionMiddleware:
    """Tests for SessionMiddleware."""
    
    def test_public_endpoint_no_auth(self, client):
        """Public endpoints should not require authentication."""
        response = client.get("/")
        assert response.status_code == 200
        assert response.json() == {"service": "m-autofill", "status": "running"}
        
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}
    
    def test_protected_endpoint_requires_auth(self, client):
        """Protected endpoints should require authentication."""
        response = client.get("/session/stats")
        print(f"Status: {response.status_code}, Body: {response.text}")
        assert response.status_code == 401
        assert "Missing authorization token" in response.json()["detail"]
    
    def test_invalid_token_format(self, client):
        """Invalid token format should be rejected."""
        # Missing 'Bearer' prefix
        response = client.get(
            "/session/stats",
            headers={"Authorization": "invalid-token"}
        )
        assert response.status_code == 401
    
    def test_expired_token(self, client, expired_token):
        """Expired tokens should be rejected."""
        response = client.get(
            "/session/stats",
            headers={"Authorization": f"Bearer {expired_token}"}
        )
        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()
    
    def test_valid_token_creates_session(self, client, valid_token, session_manager):
        """Valid token should create session on first request."""
        # Session should not exist yet
        sessions_before = session_manager.list_sessions()
        assert len(sessions_before) == 0
        
        # Make authenticated request
        response = client.get(
            "/session/stats",
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        
        # Session should be created
        assert response.status_code == 200
        sessions_after = session_manager.list_sessions()
        assert len(sessions_after) == 1
        
        # Verify session data
        data = response.json()
        assert data["user_id"] == "test_user_123"
        assert data["document_count"] == 0
        assert not data["is_expired"]
    
    def test_valid_token_reuses_existing_session(self, client, valid_token, session_manager):
        """Valid token should reuse existing session on subsequent requests."""
        # First request creates session
        response1 = client.get(
            "/session/stats",
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert response1.status_code == 200
        session_id_1 = response1.json()["session_id"]
        
        # Second request reuses same session
        response2 = client.get(
            "/session/stats",
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert response2.status_code == 200
        session_id_2 = response2.json()["session_id"]
        
        assert session_id_1 == session_id_2
        
        # Should still be only one session
        sessions = session_manager.list_sessions()
        assert len(sessions) == 1


class TestSessionEndpoints:
    """Tests for session management endpoints."""
    
    def test_get_session_stats(self, client, valid_token):
        """GET /session/stats should return session statistics."""
        response = client.get(
            "/session/stats",
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "session_id" in data
        assert "user_id" in data
        assert "created_at" in data
        assert "expires_at" in data
        assert "remaining_hours" in data
        assert "is_expired" in data
        assert "document_count" in data
        assert "isolation_scope" in data
        
        # Verify values
        assert data["user_id"] == "test_user_123"
        assert data["document_count"] == 0
        assert not data["is_expired"]
        assert data["remaining_hours"] > 23.9  # Should be close to 24 hours
    
    def test_delete_session(self, client, valid_token, session_manager):
        """DELETE /session should delete session and all data."""
        # Create session by making authenticated request
        response1 = client.get(
            "/session/stats",
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert response1.status_code == 200
        session_id = response1.json()["session_id"]
        
        # Verify session exists
        sessions_before = session_manager.list_sessions()
        assert len(sessions_before) == 1
        
        # Delete session
        response2 = client.delete(
            "/session",
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert response2.status_code == 200
        data = response2.json()
        
        assert data["session_id"] == session_id
        assert data["deleted"] is True
        assert "successfully deleted" in data["message"]
        
        # Verify session is gone
        sessions_after = session_manager.list_sessions()
        assert len(sessions_after) == 0
    
    def test_delete_nonexistent_session(self, client, valid_token, session_manager):
        """DELETE /session on nonexistent session should handle gracefully."""
        # Don't create session first - just try to delete
        # Middleware will try to create it first, then we delete it
        response = client.delete(
            "/session",
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        
        # Should succeed (session was created by middleware, then deleted)
        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] is True


class TestSessionIsolation:
    """Tests for session isolation between users."""
    
    def test_different_users_get_different_sessions(self, client, jwt_secret):
        """Different users should get isolated sessions."""
        # Create tokens for two different users
        token1 = create_token(
            user_id="user_1",
            session_id="session_1",
            org="test_org"
        )
        token2 = create_token(
            user_id="user_2",
            session_id="session_2",
            org="test_org"
        )
        
        # User 1 makes request
        response1 = client.get(
            "/session/stats",
            headers={"Authorization": f"Bearer {token1}"}
        )
        assert response1.status_code == 200
        session_id_1 = response1.json()["session_id"]
        
        # User 2 makes request
        response2 = client.get(
            "/session/stats",
            headers={"Authorization": f"Bearer {token2}"}
        )
        assert response2.status_code == 200
        session_id_2 = response2.json()["session_id"]
        
        # Sessions should be different
        assert session_id_1 != session_id_2
        
        # User IDs should be different
        assert response1.json()["user_id"] == "user_1"
        assert response2.json()["user_id"] == "user_2"


class TestMiddlewareEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_malformed_authorization_header(self, client):
        """Malformed Authorization header should be rejected."""
        # No "Bearer" prefix
        response = client.get(
            "/session/stats",
            headers={"Authorization": "abc123"}
        )
        assert response.status_code == 401
    
    def test_token_without_required_claims(self, client, jwt_secret):
        """Token without required claims should be rejected."""
        import jwt
        
        # Create token without session_id
        payload = {
            "user_id": "test_user",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1)
        }
        token = jwt.encode(payload, jwt_secret, algorithm="HS256")
        
        response = client.get(
            "/session/stats",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 401
        assert "missing required claims" in response.json()["detail"].lower()
