"""Tests for the browser-extension CORS allow-list."""

import logging

import pytest
from fastapi.testclient import TestClient

from cue_api.api import _parse_extension_origins, create_app
from m_shared.auth.middleware import SessionMiddleware
from m_shared.session.manager import SessionManager


@pytest.fixture
def session_manager(tmp_path):
    return SessionManager(base_path=str(tmp_path / "sessions"))


@pytest.fixture
def jwt_secret(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret-key")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("JWT_EXPIRATION_HOURS", "24")
    return "test-secret-key"


class TestParseExtensionOrigins:
    def test_empty_string_yields_empty_list(self):
        assert _parse_extension_origins("") == []

    def test_whitespace_only_yields_empty_list(self):
        assert _parse_extension_origins("   ,  ,  ") == []

    def test_chrome_extension_origin_accepted(self):
        result = _parse_extension_origins("chrome-extension://abcdef0123456789")
        assert result == ["chrome-extension://abcdef0123456789"]

    def test_moz_extension_origin_accepted(self):
        result = _parse_extension_origins("moz-extension://12345-6789-abcd")
        assert result == ["moz-extension://12345-6789-abcd"]

    def test_comma_split_multiple_origins(self):
        result = _parse_extension_origins("chrome-extension://abc,moz-extension://def")
        assert result == ["chrome-extension://abc", "moz-extension://def"]

    def test_whitespace_around_entries_stripped(self):
        result = _parse_extension_origins("  chrome-extension://abc , moz-extension://def  ")
        assert result == ["chrome-extension://abc", "moz-extension://def"]

    def test_wildcard_entry_dropped_with_warning(self, caplog):
        caplog.set_level(logging.WARNING, logger="cue_api.api")
        result = _parse_extension_origins("chrome-extension://*")
        assert result == []
        assert any(
            "wildcard" in r.message.lower() for r in caplog.records
        ), "Expected a warning naming the wildcard rejection"

    def test_partial_wildcard_in_middle_dropped(self, caplog):
        caplog.set_level(logging.WARNING, logger="cue_api.api")
        result = _parse_extension_origins("chrome-extension://good,chrome-extension://bad*entry")
        assert result == ["chrome-extension://good"]
        assert any("wildcard" in r.message.lower() for r in caplog.records)

    def test_disallowed_scheme_dropped_with_warning(self, caplog):
        caplog.set_level(logging.WARNING, logger="cue_api.api")
        result = _parse_extension_origins("https://example.com")
        assert result == []
        assert any(
            "chrome-extension://" in r.message or "moz-extension://" in r.message
            for r in caplog.records
        )

    def test_mixed_valid_invalid_keeps_only_valid(self, caplog):
        caplog.set_level(logging.WARNING, logger="cue_api.api")
        result = _parse_extension_origins(
            "chrome-extension://valid,https://nope.com,moz-extension://also-valid,chrome-extension://*"
        )
        assert result == [
            "chrome-extension://valid",
            "moz-extension://also-valid",
        ]


class TestCORSEndToEnd:
    def test_preflight_rejected_when_no_origins_configured(self, session_manager, monkeypatch):
        monkeypatch.delenv("EXTENSION_ALLOWED_ORIGINS", raising=False)
        app = create_app(session_manager)
        client = TestClient(app)
        response = client.options(
            "/health",
            headers={
                "Origin": "chrome-extension://abcdef",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )
        assert response.headers.get("access-control-allow-origin") is None

    def test_preflight_accepted_for_configured_origin(self, session_manager, monkeypatch):
        monkeypatch.setenv("EXTENSION_ALLOWED_ORIGINS", "chrome-extension://abcdef0123456789")
        app = create_app(session_manager)
        client = TestClient(app)
        response = client.options(
            "/health",
            headers={
                "Origin": "chrome-extension://abcdef0123456789",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )
        assert response.status_code == 200
        assert (
            response.headers.get("access-control-allow-origin")
            == "chrome-extension://abcdef0123456789"
        )
        assert response.headers.get("access-control-allow-credentials") == "true"

    def test_preflight_accepted_for_moz_extension_origin(self, session_manager, monkeypatch):
        moz_origin = "moz-extension://cue-form-filler@expat-geant.local"
        monkeypatch.setenv("EXTENSION_ALLOWED_ORIGINS", moz_origin)
        app = create_app(session_manager)
        client = TestClient(app)
        response = client.options(
            "/health",
            headers={
                "Origin": moz_origin,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == moz_origin
        assert response.headers.get("access-control-allow-credentials") == "true"

    def test_actual_request_carries_cors_header_for_allowed_origin(
        self, session_manager, monkeypatch
    ):
        monkeypatch.setenv("EXTENSION_ALLOWED_ORIGINS", "chrome-extension://abcdef0123456789")
        app = create_app(session_manager)
        client = TestClient(app)
        response = client.get(
            "/health",
            headers={"Origin": "chrome-extension://abcdef0123456789"},
        )
        assert response.status_code == 200
        assert (
            response.headers.get("access-control-allow-origin")
            == "chrome-extension://abcdef0123456789"
        )

    def test_actual_request_no_cors_header_for_unlisted_origin(self, session_manager, monkeypatch):
        monkeypatch.setenv("EXTENSION_ALLOWED_ORIGINS", "chrome-extension://allowed-only")
        app = create_app(session_manager)
        client = TestClient(app)
        response = client.get(
            "/health",
            headers={"Origin": "chrome-extension://rogue"},
        )
        # CORSMiddleware does not block non-preflight requests server-side; the
        # browser enforces. We just confirm the server did NOT echo the rogue
        # origin into Access-Control-Allow-Origin.
        assert response.headers.get("access-control-allow-origin") != "chrome-extension://rogue"

    def test_wildcard_entry_in_env_does_not_grant_access(self, session_manager, monkeypatch):
        monkeypatch.setenv("EXTENSION_ALLOWED_ORIGINS", "chrome-extension://*")
        app = create_app(session_manager)
        client = TestClient(app)
        response = client.options(
            "/health",
            headers={
                "Origin": "chrome-extension://anything",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )
        assert response.headers.get("access-control-allow-origin") is None


class TestPreflightOnProtectedPaths:
    """Preflight OPTIONS requests must bypass SessionMiddleware so CORS can
    short-circuit them. Without this bypass, browsers would receive 401 on
    preflight and never attempt the real request."""

    def test_preflight_on_protected_path_returns_cors_when_allowed(
        self, session_manager, jwt_secret, monkeypatch
    ):
        del jwt_secret  # fixture only sets env for SessionMiddleware
        monkeypatch.setenv("EXTENSION_ALLOWED_ORIGINS", "chrome-extension://abcdef0123456789")
        app = create_app(session_manager)
        app.add_middleware(SessionMiddleware, session_manager=session_manager, ttl_hours=24)
        client = TestClient(app)
        response = client.options(
            "/extract-form",
            headers={
                "Origin": "chrome-extension://abcdef0123456789",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )
        assert response.status_code == 200
        assert (
            response.headers.get("access-control-allow-origin")
            == "chrome-extension://abcdef0123456789"
        )

    def test_preflight_on_protected_path_no_401_when_origin_not_listed(
        self, session_manager, jwt_secret, monkeypatch
    ):
        del jwt_secret
        monkeypatch.delenv("EXTENSION_ALLOWED_ORIGINS", raising=False)
        app = create_app(session_manager)
        app.add_middleware(SessionMiddleware, session_manager=session_manager, ttl_hours=24)
        client = TestClient(app)
        response = client.options(
            "/extract-form",
            headers={
                "Origin": "chrome-extension://rogue",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization",
            },
        )
        # SessionMiddleware bypasses; CORSMiddleware (with no allow-list)
        # returns 400 "Disallowed CORS origin" — never 401.
        assert response.status_code != 401
