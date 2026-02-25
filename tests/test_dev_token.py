"""Tests for development token endpoint."""

import os

import pytest
from fastapi.testclient import TestClient

from m_autofill.api import create_app
from m_shared.auth.jwt_handler import validate_token
from m_shared.session.manager import SessionManager


@pytest.fixture
def client(tmp_path):
    """Create test client with temporary session storage."""
    os.environ["JWT_SECRET"] = "test_secret_key_for_dev_token"
    os.environ["ENVIRONMENT"] = "development"

    session_manager = SessionManager(base_path=str(tmp_path / "sessions"))
    app = create_app(session_manager=session_manager)

    return TestClient(app)


def test_dev_token_generation_success(client):
    """Test successful token generation in development mode."""
    response = client.post(
        "/dev/token", json={"user_id": "test_user", "org": "test_org", "roles": ["respondent"]}
    )

    assert response.status_code == 200
    data = response.json()

    assert "token" in data
    assert data["user_id"] == "test_user"
    assert data["expires_in_hours"] == 24
    assert "Bearer" in data["message"]

    # Verify token is valid
    token_claims = validate_token(data["token"])
    assert token_claims["user_id"] == "test_user"
    assert token_claims["org"] == "test_org"
    assert token_claims["roles"] == ["respondent"]


def test_dev_token_with_defaults(client):
    """Test token generation with default parameters."""
    response = client.post("/dev/token", json={})

    assert response.status_code == 200
    data = response.json()

    assert data["user_id"] == "dev_user"

    # Verify token has defaults
    token_claims = validate_token(data["token"])
    assert token_claims["user_id"] == "dev_user"
    assert token_claims["org"] == "dev_org"
    assert token_claims["roles"] == ["respondent"]


def test_dev_token_blocked_in_production(client, tmp_path):
    """Test that token endpoint returns 403 in production mode."""
    os.environ["ENVIRONMENT"] = "production"

    # Create new client with production environment
    session_manager = SessionManager(base_path=str(tmp_path / "sessions_prod"))
    app = create_app(session_manager=session_manager)
    prod_client = TestClient(app)

    response = prod_client.post("/dev/token", json={"user_id": "test_user"})

    assert response.status_code == 403
    assert "disabled in production" in response.json()["detail"]

    # Cleanup
    os.environ["ENVIRONMENT"] = "development"


def test_generated_token_can_authenticate(client):
    """Test that generated token can be used for authenticated requests."""
    # Generate token
    response = client.post("/dev/token", json={"user_id": "auth_test_user"})

    assert response.status_code == 200
    token = response.json()["token"]

    # Verify token is valid by decoding it
    token_claims = validate_token(token)
    assert token_claims["user_id"] == "auth_test_user"
    assert "session_id" in token_claims

    # Note: Testing actual authenticated requests requires middleware setup
    # which is done in test_session_api.py. Here we just verify the token is valid.


def test_dev_token_custom_expiration(client, tmp_path):
    """Test token generation with custom expiration."""
    os.environ["JWT_EXPIRATION_HOURS"] = "48"

    # Create new client with custom expiration
    session_manager = SessionManager(base_path=str(tmp_path / "sessions_exp"))
    app = create_app(session_manager=session_manager)
    exp_client = TestClient(app)

    response = exp_client.post("/dev/token", json={"user_id": "exp_user"})

    assert response.status_code == 200
    data = response.json()
    assert data["expires_in_hours"] == 48

    # Cleanup
    os.environ["JWT_EXPIRATION_HOURS"] = "24"
