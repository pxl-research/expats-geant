"""Tests for /auth/token endpoint."""

import pytest
from fastapi.testclient import TestClient

from cue_api.api import create_app
from m_shared.auth.jwt_handler import validate_token
from m_shared.session.manager import SessionManager


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Create test client."""
    monkeypatch.setenv("JWT_SECRET", "test_secret_key_for_auth_token")
    monkeypatch.setenv("API_SECRET", "test-api-secret")

    session_manager = SessionManager(base_path=str(tmp_path / "sessions"))
    app = create_app(session_manager=session_manager)

    with TestClient(app) as c:
        yield c


def test_auth_token_generation_success(client):
    """Test successful token generation with correct API secret."""
    response = client.post(
        "/auth/token", json={"user_id": "test_user", "api_secret": "test-api-secret"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert data["user_id"] == "test_user"

    token_claims = validate_token(data["token"])
    assert token_claims["user_id"] == "test_user"
    assert token_claims["org"] == "api"


def test_auth_token_wrong_secret(client):
    """Test that wrong API secret returns 401."""
    response = client.post(
        "/auth/token", json={"user_id": "test_user", "api_secret": "wrong-secret"}
    )

    assert response.status_code == 401


def test_auth_token_missing_secret(tmp_path, monkeypatch):
    """Test that missing API_SECRET env var returns 401."""
    monkeypatch.setenv("JWT_SECRET", "test_secret_key_for_auth_token")
    monkeypatch.delenv("API_SECRET", raising=False)

    session_manager = SessionManager(base_path=str(tmp_path / "sessions"))
    app = create_app(session_manager=session_manager)

    with TestClient(app) as no_secret_client:
        response = no_secret_client.post(
            "/auth/token", json={"user_id": "test_user", "api_secret": "any-value"}
        )

    assert response.status_code == 401


def test_generated_token_can_authenticate(client):
    """Test that generated token contains required claims."""
    response = client.post(
        "/auth/token", json={"user_id": "auth_test_user", "api_secret": "test-api-secret"}
    )

    assert response.status_code == 200
    token = response.json()["token"]

    token_claims = validate_token(token)
    assert token_claims["user_id"] == "auth_test_user"
    assert "session_id" in token_claims
