"""Integration tests for Cue API web URL ingest routes."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from cue_api.api import create_app
from cue_api.web_fetch import ExtractedContent, FetchResult, UnsupportedMediaType
from m_shared.auth.jwt_handler import create_token
from m_shared.auth.middleware import SessionMiddleware
from m_shared.session.manager import SessionManager
from m_shared.utils.audit import AuditEventType


@pytest.fixture
def jwt_secret(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret-key")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("JWT_EXPIRATION_HOURS", "24")
    return "test-secret-key"


@pytest.fixture
def session_manager(tmp_path):
    return SessionManager(base_path=str(tmp_path / "sessions"))


def _build_app(session_manager, *, web_enabled: bool, monkeypatch):
    monkeypatch.setenv("CUE_WEB_INGEST_ENABLED", "true" if web_enabled else "false")
    app = create_app(session_manager, audit_logger=session_manager.audit_logger)
    app.add_middleware(SessionMiddleware, session_manager=session_manager, ttl_hours=24)
    return app


def _token(user_id: str = "user_a", session_id: str = "sess_a") -> str:
    return create_token(
        user_id=user_id, session_id=session_id, org="test_org", roles=["respondent"]
    )


def _seed_session(session_manager, user_id: str, session_id: str, *, web_consent: bool):
    session = session_manager.create_session(
        user_id=user_id, ttl_hours=24, explicit_session_id=session_id
    )
    session.metadata["web_consent"] = web_consent
    session_manager._save_session_metadata(session)
    return session


def _grant_token() -> dict:
    return {"Authorization": f"Bearer {_token()}"}


@pytest.fixture
def html_fetch_patch():
    """Patch fetch_url + route_extractor to return a deterministic HTML preview."""
    fr = FetchResult(
        initial_url="https://example.com/article",
        final_url="https://example.com/article",
        content_type="text/html",
        body=b"<html><body><p>body</p></body></html>",
    )
    ec = ExtractedContent(
        text="This is the body content of the article. " * 20,
        title="My Article",
        extracted_chars=820,
    )

    async def _fake_fetch(url, *, max_bytes):
        return fr

    def _fake_extract(result):
        return ec

    with (
        patch("cue_api.routes.web.fetch_url", side_effect=_fake_fetch),
        patch("cue_api.routes.web.route_extractor", side_effect=_fake_extract),
    ):
        yield fr, ec


class TestGating:
    def test_preview_blocked_when_operator_flag_off(self, jwt_secret, session_manager, monkeypatch):
        app = _build_app(session_manager, web_enabled=False, monkeypatch=monkeypatch)
        _seed_session(session_manager, "user_a", "sess_a", web_consent=True)
        with TestClient(app) as client:
            resp = client.post(
                "/web/preview",
                json={"url": "https://example.com/x"},
                headers=_grant_token(),
            )
        assert resp.status_code == 403
        assert "not enabled" in resp.json()["detail"].lower()

    def test_preview_blocked_when_consent_off(self, jwt_secret, session_manager, monkeypatch):
        app = _build_app(session_manager, web_enabled=True, monkeypatch=monkeypatch)
        _seed_session(session_manager, "user_a", "sess_a", web_consent=False)
        with TestClient(app) as client:
            resp = client.post(
                "/web/preview",
                json={"url": "https://example.com/x"},
                headers=_grant_token(),
            )
        assert resp.status_code == 403
        assert "consent" in resp.json()["detail"].lower()

    def test_ingest_blocked_when_consent_off(self, jwt_secret, session_manager, monkeypatch):
        app = _build_app(session_manager, web_enabled=True, monkeypatch=monkeypatch)
        _seed_session(session_manager, "user_a", "sess_a", web_consent=False)
        with TestClient(app) as client:
            resp = client.post(
                "/web/ingest",
                json={"url": "https://example.com/x"},
                headers=_grant_token(),
            )
        assert resp.status_code == 403


class TestPreviewAndIngestHappyPath:
    def test_preview_returns_payload_without_storing(
        self, jwt_secret, session_manager, monkeypatch, html_fetch_patch
    ):
        app = _build_app(session_manager, web_enabled=True, monkeypatch=monkeypatch)
        _seed_session(session_manager, "user_a", "sess_a", web_consent=True)
        with TestClient(app) as client:
            resp = client.post(
                "/web/preview",
                json={"url": "https://example.com/article"},
                headers=_grant_token(),
            )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["title"] == "My Article"
        assert body["content_type"] == "text/html"
        assert body["final_url"] == "https://example.com/article"
        assert body["hostname"] == "example.com"
        assert body["extracted_chars"] == 820
        assert len(body["preview_text"]) <= 500
        assert body["already_ingested_at"] is None
        assert "likely_js_rendered" not in body["warnings"]

        store = session_manager.get_vector_store("sess_a")
        assert store.list_documents() == []

        entries = session_manager.audit_logger.get_entries("sess_a")
        web_fetches = [e for e in entries if e.event_type == AuditEventType.WEB_FETCH]
        assert len(web_fetches) == 1
        assert web_fetches[0].details["ingested"] is False

    def test_ingest_stores_chunks_and_emits_audit(
        self, jwt_secret, session_manager, monkeypatch, html_fetch_patch
    ):
        app = _build_app(session_manager, web_enabled=True, monkeypatch=monkeypatch)
        _seed_session(session_manager, "user_a", "sess_a", web_consent=True)
        with TestClient(app) as client:
            client.post(
                "/web/preview",
                json={"url": "https://example.com/article"},
                headers=_grant_token(),
            )
            resp = client.post(
                "/web/ingest",
                json={"url": "https://example.com/article"},
                headers=_grant_token(),
            )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "success"
        assert body["source_url"] == "https://example.com/article"

        store = session_manager.get_vector_store("sess_a")
        assert store.list_documents() == ["my-article"]

        web_fetches = [
            e
            for e in session_manager.audit_logger.get_entries("sess_a")
            if e.event_type == AuditEventType.WEB_FETCH
        ]
        assert [e.details["ingested"] for e in web_fetches] == [False, True]

    def test_reingest_overwrites_and_keeps_audit_history(
        self, jwt_secret, session_manager, monkeypatch, html_fetch_patch
    ):
        app = _build_app(session_manager, web_enabled=True, monkeypatch=monkeypatch)
        _seed_session(session_manager, "user_a", "sess_a", web_consent=True)
        with TestClient(app) as client:
            for _ in range(2):
                client.post(
                    "/web/preview",
                    json={"url": "https://example.com/article"},
                    headers=_grant_token(),
                )
                client.post(
                    "/web/ingest",
                    json={"url": "https://example.com/article"},
                    headers=_grant_token(),
                )

        store = session_manager.get_vector_store("sess_a")
        assert store.list_documents() == ["my-article"]

        web_fetches = [
            e
            for e in session_manager.audit_logger.get_entries("sess_a")
            if e.event_type == AuditEventType.WEB_FETCH
        ]
        assert len(web_fetches) == 4
        assert [e.details["ingested"] for e in web_fetches] == [False, True, False, True]

    def test_preview_surfaces_prior_ingest_timestamp(
        self, jwt_secret, session_manager, monkeypatch, html_fetch_patch
    ):
        app = _build_app(session_manager, web_enabled=True, monkeypatch=monkeypatch)
        _seed_session(session_manager, "user_a", "sess_a", web_consent=True)
        with TestClient(app) as client:
            client.post(
                "/web/preview",
                json={"url": "https://example.com/article"},
                headers=_grant_token(),
            )
            client.post(
                "/web/ingest",
                json={"url": "https://example.com/article"},
                headers=_grant_token(),
            )
            resp = client.post(
                "/web/preview",
                json={"url": "https://example.com/article"},
                headers=_grant_token(),
            )
        assert resp.status_code == 200
        assert resp.json()["already_ingested_at"] is not None


class TestErrorMapping:
    def test_unsupported_media_returns_415(self, jwt_secret, session_manager, monkeypatch):
        app = _build_app(session_manager, web_enabled=True, monkeypatch=monkeypatch)
        _seed_session(session_manager, "user_a", "sess_a", web_consent=True)

        async def _fake_fetch(url, *, max_bytes):
            return FetchResult(
                initial_url=url,
                final_url=url,
                content_type="image/png",
                body=b"\x89PNG",
            )

        def _fake_extract(result):
            raise UnsupportedMediaType("image/png")

        with (
            patch("cue_api.routes.web.fetch_url", side_effect=_fake_fetch),
            patch("cue_api.routes.web.route_extractor", side_effect=_fake_extract),
        ):
            with TestClient(app) as client:
                resp = client.post(
                    "/web/preview",
                    json={"url": "https://example.com/image.png"},
                    headers=_grant_token(),
                )
        assert resp.status_code == 415


class TestWebConsentEndpoint:
    def test_put_toggles_and_persists(self, jwt_secret, session_manager, monkeypatch):
        app = _build_app(session_manager, web_enabled=True, monkeypatch=monkeypatch)
        _seed_session(session_manager, "user_a", "sess_a", web_consent=False)
        with TestClient(app) as client:
            resp = client.put(
                "/session/web-consent",
                json={"enabled": True},
                headers=_grant_token(),
            )
        assert resp.status_code == 200
        assert resp.json() == {"web_consent": True}

        reloaded = session_manager.get_session("sess_a", user_id="user_a")
        assert reloaded.metadata["web_consent"] is True

    def test_stats_endpoint_includes_web_fields(self, jwt_secret, session_manager, monkeypatch):
        app = _build_app(session_manager, web_enabled=True, monkeypatch=monkeypatch)
        _seed_session(session_manager, "user_a", "sess_a", web_consent=True)
        with TestClient(app) as client:
            resp = client.get("/session/stats", headers=_grant_token())
        assert resp.status_code == 200
        body = resp.json()
        assert body["web_ingest_enabled"] is True
        assert body["web_consent"] is True

    def test_stats_defaults_when_operator_flag_off(self, jwt_secret, session_manager, monkeypatch):
        app = _build_app(session_manager, web_enabled=False, monkeypatch=monkeypatch)
        _seed_session(session_manager, "user_a", "sess_a", web_consent=False)
        with TestClient(app) as client:
            resp = client.get("/session/stats", headers=_grant_token())
        assert resp.status_code == 200
        body = resp.json()
        assert body["web_ingest_enabled"] is False
        assert body["web_consent"] is False
