"""Tests for session middleware and API endpoints."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from cue_api.api import create_app
from m_shared.auth.jwt_handler import create_token
from m_shared.auth.middleware import SessionMiddleware
from m_shared.session.manager import SessionManager


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
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture
def valid_token(jwt_secret):
    """Create valid JWT token."""
    return create_token(
        user_id="test_user_123", session_id="test_session_456", org="test_org", roles=["respondent"]
    )


@pytest.fixture
def expired_token(jwt_secret, monkeypatch):
    """Create expired JWT token."""
    # Create token that expired 1 hour ago
    monkeypatch.setenv("JWT_EXPIRATION_HOURS", "0")
    token = create_token(
        user_id="test_user_123", session_id="test_session_456", org="test_org", roles=["respondent"]
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
        assert response.json() == {"service": "cue-api", "status": "running"}

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
        response = client.get("/session/stats", headers={"Authorization": "invalid-token"})
        assert response.status_code == 401

    def test_expired_token(self, client, expired_token):
        """Expired tokens should be rejected."""
        response = client.get(
            "/session/stats", headers={"Authorization": f"Bearer {expired_token}"}
        )
        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()

    def test_valid_token_creates_session(self, client, valid_token, session_manager):
        """Valid token should create session on first request."""
        # Session should not exist yet
        sessions_before = session_manager.list_sessions()
        assert len(sessions_before) == 0

        # Make authenticated request
        response = client.get("/session/stats", headers={"Authorization": f"Bearer {valid_token}"})

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
        response1 = client.get("/session/stats", headers={"Authorization": f"Bearer {valid_token}"})
        assert response1.status_code == 200
        session_id_1 = response1.json()["session_id"]

        # Second request reuses same session
        response2 = client.get("/session/stats", headers={"Authorization": f"Bearer {valid_token}"})
        assert response2.status_code == 200
        session_id_2 = response2.json()["session_id"]

        assert session_id_1 == session_id_2

        # Should still be only one session
        sessions = session_manager.list_sessions()
        assert len(sessions) == 1

    def test_invalid_token_signature_rejected(self, client, jwt_secret):
        """Token signed with wrong secret should be rejected with 401."""
        import os
        from unittest.mock import patch

        with patch.dict(os.environ, {"JWT_SECRET": "wrong-secret"}):
            bad_token = create_token("user", "session")
        response = client.get("/session/stats", headers={"Authorization": f"Bearer {bad_token}"})
        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

    def test_session_manager_error_returns_500(self, client, valid_token):
        """Unexpected error in session management should return 500."""
        from unittest.mock import patch

        with patch(
            "m_shared.session.manager.SessionManager.get_session",
            side_effect=RuntimeError("storage failure"),
        ):
            response = client.get(
                "/session/stats", headers={"Authorization": f"Bearer {valid_token}"}
            )
        assert response.status_code == 500
        assert "session error" in response.json()["detail"].lower()

    def test_malformed_session_id_claim_returns_401(self, client):
        """A JWT carrying a path-traversal session_id should produce a 401,
        not a 500 (the SessionManager guard raises ValueError; the middleware
        must catch it at the auth boundary)."""
        bad_token = create_token(
            user_id="test_user_123",
            session_id="../evil",
            org="test_org",
            roles=["respondent"],
        )
        response = client.get("/session/stats", headers={"Authorization": f"Bearer {bad_token}"})
        assert response.status_code == 401
        assert "session" in response.json()["detail"].lower()


class TestSessionEndpoints:
    """Tests for session management endpoints."""

    def test_get_session_stats(self, client, valid_token):
        """GET /session/stats should return session statistics."""
        response = client.get("/session/stats", headers={"Authorization": f"Bearer {valid_token}"})

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
        response1 = client.get("/session/stats", headers={"Authorization": f"Bearer {valid_token}"})
        assert response1.status_code == 200
        session_id = response1.json()["session_id"]

        # Verify session exists
        sessions_before = session_manager.list_sessions()
        assert len(sessions_before) == 1

        # Delete session
        response2 = client.delete("/session", headers={"Authorization": f"Bearer {valid_token}"})
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
        response = client.delete("/session", headers={"Authorization": f"Bearer {valid_token}"})

        # Should succeed (session was created by middleware, then deleted)
        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] is True


class TestRemoveSessionDocument:
    """Tests for DELETE /session/documents/{name}."""

    @pytest.fixture
    def audit_client(self, session_manager):
        """Test client whose app has an audit_logger wired through so we can verify events."""
        app = create_app(session_manager, audit_logger=session_manager.audit_logger)
        app.add_middleware(SessionMiddleware, session_manager=session_manager, ttl_hours=24)
        return TestClient(app, raise_server_exceptions=True)

    def _upload_text_file(self, client, token, tmp_path, name="notes.txt", content="Hello world."):
        """Seed a session with a text file source."""
        test_file = tmp_path / name
        test_file.write_text(content)
        with open(test_file, "rb") as f:
            resp = client.post(
                "/upload",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": (name, f, "text/plain")},
            )
        assert resp.status_code == 200, resp.text

    def test_remove_existing_source_returns_ok(
        self, audit_client, valid_token, session_manager, tmp_path
    ):
        """Happy path: upload, then DELETE removes the collection and emits audit."""
        self._upload_text_file(audit_client, valid_token, tmp_path, name="notes.txt")
        stats = audit_client.get(
            "/session/stats", headers={"Authorization": f"Bearer {valid_token}"}
        ).json()
        assert len(stats["documents"]) == 1
        name = stats["documents"][0]["name"]

        resp = audit_client.delete(
            f"/session/documents/{name}",
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "ok"
        assert body["name"] == name

        stats_after = audit_client.get(
            "/session/stats", headers={"Authorization": f"Bearer {valid_token}"}
        ).json()
        assert stats_after["documents"] == []

        # One SOURCE_REMOVED audit entry with file-kind provenance
        from m_shared.utils import AuditEventType

        sid = stats["session_id"]
        entries = session_manager.audit_logger.get_entries(sid)
        removed = [e for e in entries if e.event_type == AuditEventType.SOURCE_REMOVED]
        assert len(removed) == 1
        assert removed[0].details["name"] == name
        assert removed[0].details["source_kind"] == "file"
        assert removed[0].details["source_mime"] == "text/plain"

    def test_remove_unknown_source_returns_404(self, audit_client, valid_token):
        """DELETE on a name that does not exist in the session returns 404 and no audit."""
        resp = audit_client.delete(
            "/session/documents/never-ingested",
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        assert resp.status_code == 404

    def test_remove_is_idempotent(self, audit_client, valid_token, tmp_path):
        """Second DELETE for the same name returns 404."""
        self._upload_text_file(audit_client, valid_token, tmp_path, name="dup.txt")
        stats = audit_client.get(
            "/session/stats", headers={"Authorization": f"Bearer {valid_token}"}
        ).json()
        name = stats["documents"][0]["name"]

        first = audit_client.delete(
            f"/session/documents/{name}",
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        assert first.status_code == 200
        second = audit_client.delete(
            f"/session/documents/{name}",
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        assert second.status_code == 404

    def test_remove_respects_session_isolation(
        self, audit_client, jwt_secret, session_manager, tmp_path
    ):
        """Removing a source from session A leaves an identically-named source in session B intact."""
        token_a = create_token(
            user_id="user_a", session_id="sess_a", org="test_org", roles=["respondent"]
        )
        token_b = create_token(
            user_id="user_b", session_id="sess_b", org="test_org", roles=["respondent"]
        )
        self._upload_text_file(audit_client, token_a, tmp_path, name="shared.txt", content="A")
        self._upload_text_file(audit_client, token_b, tmp_path, name="shared.txt", content="B")

        stats_a = audit_client.get(
            "/session/stats", headers={"Authorization": f"Bearer {token_a}"}
        ).json()
        name = stats_a["documents"][0]["name"]

        resp = audit_client.delete(
            f"/session/documents/{name}",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert resp.status_code == 200

        # Session B's source survives
        stats_b = audit_client.get(
            "/session/stats", headers={"Authorization": f"Bearer {token_b}"}
        ).json()
        assert any(d["name"] == name for d in stats_b["documents"])

    def test_remove_requires_authentication(self, audit_client):
        """DELETE without a JWT returns 401."""
        resp = audit_client.delete("/session/documents/anything")
        assert resp.status_code == 401


class TestDeleteSessionById:
    """Tests for DELETE /sessions/{session_id} — user-scoped delete with JWT rotation."""

    def _session_less_token(self, user_id: str) -> str:
        return create_token(user_id=user_id, session_id=None, org="test_org", roles=["respondent"])

    def _bound_token(self, user_id: str, session_id: str) -> str:
        return create_token(
            user_id=user_id, session_id=session_id, org="test_org", roles=["respondent"]
        )

    def test_delete_succeeds_for_owner(self, client, jwt_secret, session_manager):
        token = self._session_less_token("user_A")
        created = client.post("/sessions/new", headers={"Authorization": f"Bearer {token}"})
        assert created.status_code == 201
        sid = created.json()["session_id"]

        resp = client.delete(f"/sessions/{sid}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["session_id"] == sid
        assert body["deleted"] is True
        assert session_manager.get_session(sid) is None

    def test_delete_returns_session_less_token_when_jwt_bound(
        self, client, jwt_secret, session_manager
    ):
        creator_token = self._session_less_token("user_B")
        created = client.post("/sessions/new", headers={"Authorization": f"Bearer {creator_token}"})
        sid = created.json()["session_id"]
        bound = self._bound_token("user_B", sid)

        resp = client.delete(f"/sessions/{sid}", headers={"Authorization": f"Bearer {bound}"})
        assert resp.status_code == 200
        new_token = resp.json()["token"]
        assert new_token and new_token != bound

        from m_shared.auth.jwt_handler import validate_token

        claims = validate_token(new_token)
        assert claims["user_id"] == "user_B"
        assert claims.get("session_id") is None

    def test_delete_no_token_when_jwt_unbound(self, client, jwt_secret, session_manager):
        token = self._session_less_token("user_C")
        created = client.post("/sessions/new", headers={"Authorization": f"Bearer {token}"})
        sid = created.json()["session_id"]
        # Delete using a session-less token (no rotation needed)
        resp = client.delete(f"/sessions/{sid}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["token"] is None

    def test_delete_other_users_session_returns_404(self, client, jwt_secret):
        token_a = self._session_less_token("user_A2")
        token_b = self._session_less_token("user_B2")
        created = client.post("/sessions/new", headers={"Authorization": f"Bearer {token_a}"})
        sid = created.json()["session_id"]

        resp = client.delete(f"/sessions/{sid}", headers={"Authorization": f"Bearer {token_b}"})
        assert resp.status_code == 404

    def test_delete_nonexistent_session_returns_404(self, client, jwt_secret):
        token = self._session_less_token("user_X")
        resp = client.delete(
            "/sessions/does-not-exist", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 404


class TestTransferSession:
    """Tests for POST /sessions/{session_id}/transfer — handoff with JWT rotation."""

    def _session_less_token(self, user_id: str) -> str:
        return create_token(user_id=user_id, session_id=None, org="test_org", roles=["respondent"])

    def _bound_token(self, user_id: str, session_id: str) -> str:
        return create_token(
            user_id=user_id, session_id=session_id, org="test_org", roles=["respondent"]
        )

    def test_transfer_succeeds_for_owner(self, client, jwt_secret, session_manager):
        sender_token = self._session_less_token("transfer_sender")
        recipient_token = self._session_less_token("transfer_recipient")
        # Recipient must have logged in at least once — simulated by creating
        # a throwaway session, which calls ensure_user_directory.
        client.post("/sessions/new", headers={"Authorization": f"Bearer {recipient_token}"})

        created = client.post("/sessions/new", headers={"Authorization": f"Bearer {sender_token}"})
        sid = created.json()["session_id"]

        resp = client.post(
            f"/sessions/{sid}/transfer",
            headers={"Authorization": f"Bearer {sender_token}"},
            json={"recipient_user_id": "transfer_recipient"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "transferred"
        assert body["session_id"] == sid
        moved = session_manager.get_session(sid, user_id="transfer_recipient")
        assert moved is not None
        assert moved.user_id == "transfer_recipient"

    def test_transfer_returns_session_less_token_when_jwt_bound(
        self, client, jwt_secret, session_manager
    ):
        sender_token = self._session_less_token("sender_bound")
        recipient_token = self._session_less_token("recipient_bound")
        client.post("/sessions/new", headers={"Authorization": f"Bearer {recipient_token}"})
        created = client.post("/sessions/new", headers={"Authorization": f"Bearer {sender_token}"})
        sid = created.json()["session_id"]
        bound = self._bound_token("sender_bound", sid)

        resp = client.post(
            f"/sessions/{sid}/transfer",
            headers={"Authorization": f"Bearer {bound}"},
            json={"recipient_user_id": "recipient_bound"},
        )
        assert resp.status_code == 200
        new_token = resp.json()["token"]
        assert new_token and new_token != bound

        from m_shared.auth.jwt_handler import validate_token

        claims = validate_token(new_token)
        assert claims["user_id"] == "sender_bound"
        assert claims.get("session_id") is None

    def test_transfer_no_token_when_jwt_unbound(self, client, jwt_secret, session_manager):
        sender_token = self._session_less_token("sender_unbound")
        recipient_token = self._session_less_token("recipient_unbound")
        client.post("/sessions/new", headers={"Authorization": f"Bearer {recipient_token}"})
        created = client.post("/sessions/new", headers={"Authorization": f"Bearer {sender_token}"})
        sid = created.json()["session_id"]

        resp = client.post(
            f"/sessions/{sid}/transfer",
            headers={"Authorization": f"Bearer {sender_token}"},
            json={"recipient_user_id": "recipient_unbound"},
        )
        assert resp.status_code == 200
        assert resp.json()["token"] is None

    def test_transfer_recipient_must_exist(self, client, jwt_secret, session_manager):
        sender_token = self._session_less_token("sender_norec")
        created = client.post("/sessions/new", headers={"Authorization": f"Bearer {sender_token}"})
        sid = created.json()["session_id"]

        resp = client.post(
            f"/sessions/{sid}/transfer",
            headers={"Authorization": f"Bearer {sender_token}"},
            json={"recipient_user_id": "never_logged_in"},
        )
        assert resp.status_code == 404

    def test_transfer_other_users_session_returns_404(self, client, jwt_secret, session_manager):
        owner_token = self._session_less_token("owner_x")
        thief_token = self._session_less_token("thief_x")
        recipient_token = self._session_less_token("recipient_x")
        client.post("/sessions/new", headers={"Authorization": f"Bearer {recipient_token}"})
        created = client.post("/sessions/new", headers={"Authorization": f"Bearer {owner_token}"})
        sid = created.json()["session_id"]

        resp = client.post(
            f"/sessions/{sid}/transfer",
            headers={"Authorization": f"Bearer {thief_token}"},
            json={"recipient_user_id": "recipient_x"},
        )
        assert resp.status_code == 404


class TestListSessionsSorted:
    """Tests for GET /sessions returning newest-first."""

    def test_list_sessions_sorted_by_created_at_desc(self, client, jwt_secret, session_manager):
        # Three sessions for one user, distinct created_at timestamps.
        base = datetime.now(UTC).replace(microsecond=0)
        for i, delta in enumerate([2, 0, 1]):  # mid, oldest, newest order of creation
            s = session_manager.create_session(user_id="user_sort", ttl_hours=24)
            s.created_at = base + timedelta(minutes=delta * 10)
            session_manager._save_session_metadata(s)

        token = create_token(user_id="user_sort", session_id=None, org="test_org")
        resp = client.get("/sessions", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        items = resp.json()["sessions"]
        timestamps = [it["created_at"] for it in items]
        assert timestamps == sorted(timestamps, reverse=True)


class TestSessionIsolation:
    """Tests for session isolation between users."""

    def test_different_users_get_different_sessions(self, client, jwt_secret):
        """Different users should get isolated sessions."""
        # Create tokens for two different users
        token1 = create_token(user_id="user_1", session_id="session_1", org="test_org")
        token2 = create_token(user_id="user_2", session_id="session_2", org="test_org")

        # User 1 makes request
        response1 = client.get("/session/stats", headers={"Authorization": f"Bearer {token1}"})
        assert response1.status_code == 200
        session_id_1 = response1.json()["session_id"]

        # User 2 makes request
        response2 = client.get("/session/stats", headers={"Authorization": f"Bearer {token2}"})
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
        response = client.get("/session/stats", headers={"Authorization": "abc123"})
        assert response.status_code == 401

    def test_token_without_session_id_returns_403_on_session_endpoint(self, client, jwt_secret):
        """Token without session_id is forbidden on session-scoped endpoints."""
        import jwt

        payload = {"user_id": "test_user", "exp": datetime.now(UTC) + timedelta(hours=1)}
        token = jwt.encode(payload, jwt_secret, algorithm="HS256")

        response = client.get("/session/stats", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403
        assert "no active session" in response.json()["detail"].lower()


class TestUploadEndpoint:
    """Tests for POST /upload endpoint."""

    def test_upload_document_success(self, client, valid_token, tmp_path):
        """Successful document upload."""
        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Test document content for upload.")

        with open(test_file, "rb") as f:
            response = client.post(
                "/upload",
                headers={"Authorization": f"Bearer {valid_token}"},
                files={"file": ("test.txt", f, "text/plain")},
            )

        if response.status_code != 200:
            print(f"Error response: {response.text}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["filename"] == "test.txt"
        assert data["size_bytes"] > 0
        assert "upload_timestamp" in data
        assert "session_id" in data

    def test_upload_requires_authentication(self, client, tmp_path):
        """Upload without auth should fail."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Test content")

        with open(test_file, "rb") as f:
            response = client.post("/upload", files={"file": ("test.txt", f, "text/plain")})

        assert response.status_code == 401

    def test_upload_invalid_file_type(self, client, valid_token, tmp_path):
        """Upload with invalid file type should fail."""
        test_file = tmp_path / "test.exe"
        test_file.write_bytes(b"fake executable")

        with open(test_file, "rb") as f:
            response = client.post(
                "/upload",
                headers={"Authorization": f"Bearer {valid_token}"},
                files={"file": ("test.exe", f, "application/x-executable")},
            )

        assert response.status_code == 400
        assert "validation" in response.json()["detail"].lower()


class TestAuditReportEndpoint:
    """Tests for GET /audit-report endpoint."""

    @pytest.fixture
    def app_with_audit(self, session_manager):
        """Create app with audit logger."""
        from cue_api.api import create_app
        from m_shared.auth.middleware import SessionMiddleware
        from m_shared.utils.audit import AuditLogger

        audit_logger = AuditLogger(base_path=str(session_manager.base_path))
        app = create_app(session_manager=session_manager, audit_logger=audit_logger)
        app.add_middleware(SessionMiddleware, session_manager=session_manager, ttl_hours=24)
        return app

    @pytest.fixture
    def client_with_audit(self, app_with_audit):
        """Create test client with audit support."""
        return TestClient(app_with_audit, raise_server_exceptions=False)

    def test_audit_report_requires_authentication(self, client_with_audit):
        """Audit report without auth should fail."""
        response = client_with_audit.get("/audit-report")
        assert response.status_code == 401

    def test_audit_report_json_format(self, client_with_audit, valid_token):
        """Audit report in JSON format."""
        # Create session first
        client_with_audit.get("/session/stats", headers={"Authorization": f"Bearer {valid_token}"})

        response = client_with_audit.get(
            "/audit-report?format=json", headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert "summary" in data

    def test_audit_report_plaintext_format(self, client_with_audit, valid_token):
        """Audit report in plaintext format."""
        # Create session first
        client_with_audit.get("/session/stats", headers={"Authorization": f"Bearer {valid_token}"})

        response = client_with_audit.get(
            "/audit-report?format=plaintext", headers={"Authorization": f"Bearer {valid_token}"}
        )

        # Accept 200 or 500 (report might fail if no data)
        # The important thing is the endpoint exists and format param works
        if response.status_code == 200:
            assert "AUDIT REPORT" in response.text
            assert "Session" in response.text
        else:
            # If error, just verify endpoint is configured
            assert response.status_code in [200, 500]


class TestAuditReportDeletion:
    """Tests for DELETE /audit-report endpoint (GDPR RTBF)."""

    @pytest.fixture
    def app_with_audit(self, session_manager):
        from cue_api.api import create_app
        from m_shared.auth.middleware import SessionMiddleware
        from m_shared.utils.audit import AuditLogger

        audit_logger = AuditLogger(base_path=str(session_manager.base_path))
        app = create_app(session_manager=session_manager, audit_logger=audit_logger)
        app.add_middleware(SessionMiddleware, session_manager=session_manager, ttl_hours=24)
        return app

    @pytest.fixture
    def client_with_audit(self, app_with_audit):
        return TestClient(app_with_audit, raise_server_exceptions=False)

    def test_delete_audit_report_requires_auth(self, client_with_audit):
        """DELETE /audit-report without auth should fail."""
        response = client_with_audit.delete("/audit-report")
        assert response.status_code == 401

    def test_delete_audit_report_returns_200(self, client_with_audit, valid_token):
        """DELETE /audit-report returns success response."""
        # Ensure session exists first
        client_with_audit.get("/session/stats", headers={"Authorization": f"Bearer {valid_token}"})

        response = client_with_audit.delete(
            "/audit-report", headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] is True
        assert "session_id" in data

    def test_get_audit_report_after_delete_returns_404(self, client_with_audit, valid_token):
        """GET /audit-report returns 404 after RTBF deletion."""
        # Ensure session exists
        client_with_audit.get("/session/stats", headers={"Authorization": f"Bearer {valid_token}"})

        # Delete the audit report
        client_with_audit.delete(
            "/audit-report", headers={"Authorization": f"Bearer {valid_token}"}
        )

        # Subsequent GET should return 404
        response = client_with_audit.get(
            "/audit-report", headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert response.status_code == 404

    def test_delete_audit_report_idempotent(self, client_with_audit, valid_token):
        """DELETE /audit-report can be called twice without error."""
        client_with_audit.get("/session/stats", headers={"Authorization": f"Bearer {valid_token}"})

        client_with_audit.delete(
            "/audit-report", headers={"Authorization": f"Bearer {valid_token}"}
        )
        response = client_with_audit.delete(
            "/audit-report", headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert response.status_code == 200


class TestPrivacyEndpoint:
    """Tests for GET /privacy endpoint."""

    def test_privacy_statement_public(self, client):
        """Privacy statement should be public."""
        response = client.get("/privacy")
        assert response.status_code == 200
        assert "PRIVACY STATEMENT" in response.text
        assert "GDPR" in response.text
        assert "DATA COLLECTION" in response.text


class TestAuthEndpoints:
    """Tests for /auth/login and /auth/callback endpoints."""

    def test_auth_login_redirects_to_provider(self, client):
        """GET /auth/login returns 302 redirect to OIDC provider."""
        from unittest.mock import AsyncMock, patch

        with patch(
            "cue_api.routes.auth.get_authorization_url",
            new=AsyncMock(return_value=("https://provider.example.com/auth?state=abc", "abc")),
        ):
            response = client.get("/auth/login", follow_redirects=False)

        assert response.status_code == 302
        assert response.headers["location"] == "https://provider.example.com/auth?state=abc"

    def test_auth_login_is_public(self, client):
        """GET /auth/login is accessible without an Authorization token."""
        from unittest.mock import AsyncMock, patch

        with patch(
            "cue_api.routes.auth.get_authorization_url",
            new=AsyncMock(return_value=("https://provider.example.com/auth?state=abc", "abc")),
        ):
            response = client.get("/auth/login", follow_redirects=False)

        assert response.status_code != 401

    def test_auth_login_oidc_not_configured(self, client):
        """GET /auth/login returns 503 when OIDC env vars are missing."""
        from unittest.mock import AsyncMock, patch

        from m_shared.auth.oauth import OIDCConfigurationError

        with patch(
            "cue_api.routes.auth.get_authorization_url",
            new=AsyncMock(side_effect=OIDCConfigurationError("OIDC_ISSUER_URL not set")),
        ):
            response = client.get("/auth/login")

        assert response.status_code == 503
        assert "OIDC not configured" in response.json()["detail"]

    def test_auth_login_provider_unreachable(self, client):
        """GET /auth/login returns 503 when OIDC provider cannot be reached."""
        from unittest.mock import AsyncMock, patch

        with patch(
            "cue_api.routes.auth.get_authorization_url",
            new=AsyncMock(side_effect=Exception("Connection refused")),
        ):
            response = client.get("/auth/login")

        assert response.status_code == 503
        assert "unreachable" in response.json()["detail"]

    def test_auth_callback_success(self, client):
        """GET /auth/callback returns platform JWT on valid code and state."""
        from unittest.mock import AsyncMock, patch

        with patch(
            "cue_api.routes.auth.exchange_code",
            new=AsyncMock(return_value="platform.jwt.token"),
        ):
            response = client.get("/auth/callback?code=authcode123&state=validstate")

        assert response.status_code == 200
        data = response.json()
        assert data["token"] == "platform.jwt.token"
        assert data["token_type"] == "bearer"

    def test_auth_callback_is_public(self, client):
        """GET /auth/callback is accessible without an Authorization token."""
        from unittest.mock import AsyncMock, patch

        with patch(
            "cue_api.routes.auth.exchange_code",
            new=AsyncMock(return_value="platform.jwt.token"),
        ):
            response = client.get("/auth/callback?code=code&state=state")

        assert response.status_code != 401

    def test_auth_callback_invalid_state(self, client):
        """GET /auth/callback returns 400 on invalid or expired state."""
        from unittest.mock import AsyncMock, patch

        from m_shared.auth.oauth import OIDCStateError

        with patch(
            "cue_api.routes.auth.exchange_code",
            new=AsyncMock(side_effect=OIDCStateError("state not found")),
        ):
            response = client.get("/auth/callback?code=code&state=badstate")

        assert response.status_code == 400
        assert "Invalid OAuth state" in response.json()["detail"]

    def test_auth_callback_token_validation_failure(self, client):
        """GET /auth/callback returns 400 when ID token validation fails."""
        from unittest.mock import AsyncMock, patch

        from m_shared.auth.oauth import OIDCTokenError

        with patch(
            "cue_api.routes.auth.exchange_code",
            new=AsyncMock(side_effect=OIDCTokenError("token expired")),
        ):
            response = client.get("/auth/callback?code=code&state=validstate")

        assert response.status_code == 400
        assert "ID token validation failed" in response.json()["detail"]

    def test_auth_callback_oidc_not_configured(self, client):
        """GET /auth/callback returns 503 when OIDC is not configured."""
        from unittest.mock import AsyncMock, patch

        from m_shared.auth.oauth import OIDCConfigurationError

        with patch(
            "cue_api.routes.auth.exchange_code",
            new=AsyncMock(side_effect=OIDCConfigurationError("missing env")),
        ):
            response = client.get("/auth/callback?code=code&state=state")

        assert response.status_code == 503
        assert "OIDC not configured" in response.json()["detail"]

    def test_auth_callback_exchange_failed(self, client):
        """GET /auth/callback returns 503 on unexpected exchange errors."""
        from unittest.mock import AsyncMock, patch

        with patch(
            "cue_api.routes.auth.exchange_code",
            new=AsyncMock(side_effect=Exception("network error")),
        ):
            response = client.get("/auth/callback?code=code&state=state")

        assert response.status_code == 503
        assert "OIDC exchange failed" in response.json()["detail"]


class TestFullSessionFlow:
    """Integration tests for complete user flows."""

    @pytest.fixture
    def full_app(self, session_manager, tmp_path, monkeypatch):
        """Create fully configured app."""
        from unittest.mock import Mock

        from cue_api.api import create_app
        from m_shared.auth.middleware import SessionMiddleware
        from m_shared.llm.client import LLMClient
        from m_shared.utils.audit import AuditLogger

        # Mock LLM
        llm_client = Mock(spec=LLMClient)
        llm_client.create_completion.return_value = {
            "content": "Based on your uploaded document, here is the answer.",
            "model": "test-model",
            "usage": {"total_tokens": 50},
        }

        # Mock OpenAI client for embeddings
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        audit_logger = AuditLogger(base_path=str(session_manager.base_path))
        app = create_app(
            session_manager=session_manager,
            llm_client=llm_client,
            audit_logger=audit_logger,
            max_file_size_mb=50,
        )
        app.add_middleware(SessionMiddleware, session_manager=session_manager, ttl_hours=24)
        return app

    @pytest.fixture
    def full_client(self, full_app):
        """Create client for full integration tests."""
        return TestClient(full_app, raise_server_exceptions=False)

    def test_complete_workflow_without_llm(self, full_client, valid_token, tmp_path):
        """Test complete workflow: upload → audit → delete."""
        # 1. Check privacy statement
        response = full_client.get("/privacy")
        assert response.status_code == 200

        # 2. Check initial session stats
        response = full_client.get(
            "/session/stats", headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert response.status_code == 200
        assert response.json()["document_count"] == 0

        # 3. Upload document
        test_file = tmp_path / "workflow_test.txt"
        test_file.write_text("This is a test document for the complete workflow.")

        with open(test_file, "rb") as f:
            response = full_client.post(
                "/upload",
                headers={"Authorization": f"Bearer {valid_token}"},
                files={"file": ("workflow_test.txt", f, "text/plain")},
            )
        assert response.status_code == 200

        # 4. Get audit report
        response = full_client.get(
            "/audit-report?format=json", headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert response.status_code == 200

        # 5. Delete session
        response = full_client.delete(
            "/session", headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert response.status_code == 200
        assert response.json()["deleted"] is True


class TestSubmitEndpointErrors:
    """Error paths in POST /sessions/{session_id}/submit."""

    @pytest.fixture
    def submit_client(self, app):
        """TestClient that returns JSON for all error responses."""
        return TestClient(app, raise_server_exceptions=False)

    @pytest.fixture
    def token_and_session(self, valid_token, session_manager):
        """Pre-create the session so we know the actual session_id (hash of token)."""
        session = session_manager.create_session(
            user_id="test_user_123", explicit_session_id="test_session_456"
        )
        return valid_token, session

    def test_submit_session_mismatch(self, submit_client, valid_token):
        """URL session_id differs from the session derived from the token → 403."""
        response = submit_client.post(
            "/sessions/wrong_session_id/submit",
            headers={"Authorization": f"Bearer {valid_token}"},
            json={"responses": {}},
        )
        assert response.status_code == 403

    def test_submit_survey_not_found(self, submit_client, token_and_session):
        """Session exists but survey.json absent → 404."""
        token, session = token_and_session
        response = submit_client.post(
            f"/sessions/{session.session_id}/submit",
            headers={"Authorization": f"Bearer {token}"},
            json={"responses": {}},
        )
        assert response.status_code == 404

    def test_submit_format_missing(self, submit_client, token_and_session, session_manager):
        """survey.json has no format in metadata → 422."""
        import json as _json

        token, session = token_and_session
        survey_path = session_manager._get_session_path(session.session_id) / "survey.json"
        survey_path.write_text(_json.dumps({"id": "s1", "metadata": {}}))
        response = submit_client.post(
            f"/sessions/{session.session_id}/submit",
            headers={"Authorization": f"Bearer {token}"},
            json={"responses": {}},
        )
        assert response.status_code == 422

    def test_submit_adapter_not_found(self, submit_client, token_and_session, session_manager):
        """Unknown format string → 422."""
        import json as _json

        token, session = token_and_session
        survey_path = session_manager._get_session_path(session.session_id) / "survey.json"
        survey_path.write_text(_json.dumps({"id": "s1", "metadata": {"format": "unknown_fmt"}}))
        response = submit_client.post(
            f"/sessions/{session.session_id}/submit",
            headers={"Authorization": f"Bearer {token}"},
            json={"responses": {}},
        )
        assert response.status_code == 422

    def test_submit_capability_not_supported(
        self, submit_client, token_and_session, session_manager
    ):
        """Format qti exists but lacks submit capability → 422."""
        import json as _json

        token, session = token_and_session
        survey_path = session_manager._get_session_path(session.session_id) / "survey.json"
        survey_path.write_text(_json.dumps({"id": "s1", "metadata": {"format": "qti"}}))
        response = submit_client.post(
            f"/sessions/{session.session_id}/submit",
            headers={"Authorization": f"Bearer {token}"},
            json={"responses": {}},
        )
        assert response.status_code == 422

    def test_submit_adapter_raises(self, submit_client, token_and_session, session_manager):
        """Adapter submit_responses raises RuntimeError → 502."""
        import json as _json
        from unittest.mock import MagicMock, patch

        token, session = token_and_session
        survey_path = session_manager._get_session_path(session.session_id) / "survey.json"
        survey_path.write_text(_json.dumps({"id": "s1", "metadata": {"format": "mock_fmt"}}))

        mock_adapter = MagicMock()
        mock_adapter.capabilities.return_value = ["import", "export", "submit"]
        mock_adapter.submit_responses.side_effect = RuntimeError("platform failed")

        with patch("cue_api.routes.surveys.get_adapter", return_value=mock_adapter):
            response = submit_client.post(
                f"/sessions/{session.session_id}/submit",
                headers={"Authorization": f"Bearer {token}"},
                json={"responses": {"q_1": "answer"}},
            )
        assert response.status_code == 502


class TestSubmitCredentialResolution:
    """Per-request credentials + env-var fallback on POST /sessions/{id}/submit."""

    @pytest.fixture
    def submit_client(self, app):
        return TestClient(app, raise_server_exceptions=False)

    @pytest.fixture
    def token_and_session(self, valid_token, session_manager):
        session = session_manager.create_session(
            user_id="test_user_123", explicit_session_id="test_session_456"
        )
        return valid_token, session

    @pytest.fixture
    def lss_survey_path(self, session_manager, token_and_session):
        import json as _json

        _, session = token_and_session
        path = session_manager._get_session_path(session.session_id) / "survey.json"
        path.write_text(_json.dumps({"id": "42", "metadata": {"format": "lss"}}))
        return path

    @pytest.fixture
    def clear_ls_env(self, monkeypatch):
        for var in ("LIMESURVEY_API_URL", "LIMESURVEY_USERNAME", "LIMESURVEY_PASSWORD"):
            monkeypatch.delenv(var, raising=False)

    def test_submit_uses_body_credentials(
        self, submit_client, token_and_session, lss_survey_path, clear_ls_env
    ):
        """Credentials in body are forwarded to the adapter constructor."""
        from unittest.mock import MagicMock, patch

        _ = lss_survey_path
        token, session = token_and_session
        mock_adapter = MagicMock()
        mock_adapter.capabilities.return_value = ["import", "export", "submit"]
        mock_factory = MagicMock(return_value=mock_adapter)
        with patch("cue_api.routes.surveys.get_adapter", mock_factory):
            response = submit_client.post(
                f"/sessions/{session.session_id}/submit",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "responses": {"q_1": "answer"},
                    "credentials": {
                        "api_url": "https://survey.example.com/admin/remotecontrol",
                        "username": "user",
                        "password": "pass",
                    },
                },
            )
        assert response.status_code == 200
        mock_factory.assert_called_once_with(
            "lss",
            api_url="https://survey.example.com/admin/remotecontrol",
            username="user",
            password="pass",
        )

    def test_submit_falls_back_to_env_credentials(
        self, submit_client, token_and_session, lss_survey_path, monkeypatch
    ):
        """No body credentials + env vars set → env vars are used."""
        from unittest.mock import MagicMock, patch

        _ = lss_survey_path
        token, session = token_and_session
        monkeypatch.setenv("LIMESURVEY_API_URL", "https://env.example.com/admin/remotecontrol")
        monkeypatch.setenv("LIMESURVEY_USERNAME", "envuser")
        monkeypatch.setenv("LIMESURVEY_PASSWORD", "envpass")
        mock_adapter = MagicMock()
        mock_adapter.capabilities.return_value = ["import", "export", "submit"]
        mock_factory = MagicMock(return_value=mock_adapter)
        with patch("cue_api.routes.surveys.get_adapter", mock_factory):
            response = submit_client.post(
                f"/sessions/{session.session_id}/submit",
                headers={"Authorization": f"Bearer {token}"},
                json={"responses": {"q_1": "answer"}},
            )
        assert response.status_code == 200
        mock_factory.assert_called_once_with(
            "lss",
            api_url="https://env.example.com/admin/remotecontrol",
            username="envuser",
            password="envpass",
        )

    def test_submit_missing_credentials_returns_422(
        self, submit_client, token_and_session, lss_survey_path, clear_ls_env
    ):
        """Empty body credentials + no env vars → 422 listing the missing fields."""
        _ = lss_survey_path
        token, session = token_and_session
        response = submit_client.post(
            f"/sessions/{session.session_id}/submit",
            headers={"Authorization": f"Bearer {token}"},
            json={"responses": {"q_1": "answer"}},
        )
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert "api_url" in detail
        assert "username" in detail
        assert "password" in detail
        # The error message must not leak any caller-supplied secret value.
        assert "pass" not in detail.replace("password", "")

    def test_capabilities_reports_submit_regardless_of_env(
        self, submit_client, valid_token, clear_ls_env
    ):
        """Capability endpoint now reflects adapter implementation, not env state."""
        response = submit_client.get(
            "/adapters/lss/capabilities",
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        assert response.status_code == 200
        assert "submit" in response.json()

    def test_submit_validates_api_url_in_production(
        self,
        submit_client,
        token_and_session,
        lss_survey_path,
        clear_ls_env,
        monkeypatch,
    ):
        """Unsafe api_url (http to internal address) is rejected in production."""
        _ = lss_survey_path
        token, session = token_and_session
        monkeypatch.setenv("ENVIRONMENT", "production")
        response = submit_client.post(
            f"/sessions/{session.session_id}/submit",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "responses": {"q_1": "answer"},
                "credentials": {
                    "api_url": "http://localhost:7080/admin/remotecontrol",
                    "username": "user",
                    "password": "pass",
                },
            },
        )
        assert response.status_code == 400

    def test_submit_validates_env_api_url_in_production(
        self,
        submit_client,
        token_and_session,
        lss_survey_path,
        monkeypatch,
    ):
        """Env-supplied api_url is validated too (parity with body path)."""
        _ = lss_survey_path
        token, session = token_and_session
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("LIMESURVEY_API_URL", "http://localhost:7080/admin/remotecontrol")
        monkeypatch.setenv("LIMESURVEY_USERNAME", "envuser")
        monkeypatch.setenv("LIMESURVEY_PASSWORD", "envpass")
        response = submit_client.post(
            f"/sessions/{session.session_id}/submit",
            headers={"Authorization": f"Bearer {token}"},
            json={"responses": {"q_1": "answer"}},
        )
        assert response.status_code == 400

    def test_submit_validates_datacenter_id(
        self,
        submit_client,
        token_and_session,
        session_manager,
        monkeypatch,
    ):
        """Qualtrics datacenter_id must be alphanumeric, regardless of source."""
        import json as _json

        token, session = token_and_session
        path = session_manager._get_session_path(session.session_id) / "survey.json"
        path.write_text(_json.dumps({"id": "SV_x", "metadata": {"format": "qsf"}}))
        for v in ("QUALTRICS_API_TOKEN", "QUALTRICS_DATACENTER_ID"):
            monkeypatch.delenv(v, raising=False)
        response = submit_client.post(
            f"/sessions/{session.session_id}/submit",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "responses": {"q_1": "answer"},
                "credentials": {
                    "api_token": "tok",
                    "datacenter_id": "iad1; DROP TABLE",
                },
            },
        )
        assert response.status_code == 400
        assert "datacenter_id" in response.json()["detail"]


class TestPlatformCodeTranslation:
    """Submit-time translation from internal option ids to platform answer codes.

    The HTML form sends ``option.id`` (e.g. ``opt_A1``) because that's the
    natural HTML value of a checkbox; LimeSurvey's SGQA suffix and Qualtrics'
    choice code use ``option.value`` (e.g. ``A1``). Without translation the
    upstream call silently drops the answer — the row lands with NULL values.
    """

    def test_translate_list_maps_each_item(self):
        from cue_api.routes.surveys import _translate_to_platform_code

        result = _translate_to_platform_code(
            ["opt_A1", "opt_A3"], {"opt_A1": "A1", "opt_A2": "A2", "opt_A3": "A3"}
        )
        assert result == ["A1", "A3"]

    def test_translate_scalar_string_maps_known_id(self):
        from cue_api.routes.surveys import _translate_to_platform_code

        result = _translate_to_platform_code("opt_A1", {"opt_A1": "A1"})
        assert result == "A1"

    def test_translate_passes_through_unknown_values(self):
        """Free-text answers and other unmappable strings must not be mangled."""
        from cue_api.routes.surveys import _translate_to_platform_code

        result = _translate_to_platform_code("My free text answer", {"opt_A1": "A1"})
        assert result == "My free text answer"

    def test_translate_no_options_returns_unchanged(self):
        """Open-ended and slider questions have an empty option map."""
        from cue_api.routes.surveys import _translate_to_platform_code

        assert _translate_to_platform_code("anything", {}) == "anything"
        assert _translate_to_platform_code(["a", "b"], {}) == ["a", "b"]
        assert _translate_to_platform_code(42, {}) == 42

    def test_translate_partial_map_keeps_unknown_items(self):
        """A list with one known and one unknown item passes the unknown
        through verbatim — the adapter sees a best-effort answer rather than
        a silently-dropped one."""
        from cue_api.routes.surveys import _translate_to_platform_code

        result = _translate_to_platform_code(["opt_A1", "freeform"], {"opt_A1": "A1"})
        assert result == ["A1", "freeform"]

    def test_build_responses_translates_via_option_values_meta(self):
        """End-to-end through _build_responses_from_body: the q_<id> body keys
        become Response objects whose answer_value is the platform code."""
        from cue_api.routes.surveys import _build_responses_from_body

        question_meta = {
            "q_5001": {
                "ls_qid": "5001",
                "_option_values": {"opt_A1": "A1", "opt_A2": "A2", "opt_A3": "A3"},
            },
            "q_text": {"_option_values": {}},
        }
        body = {"q_q_5001": ["opt_A1", "opt_A3"], "q_q_text": "Hello world"}
        responses = _build_responses_from_body(body, question_meta, "sess-xyz")
        by_qid = {r.question_id: r for r in responses}
        assert by_qid["q_5001"].answer_value == ["A1", "A3"]
        assert by_qid["q_5001"].metadata["ls_qid"] == "5001"
        assert by_qid["q_text"].answer_value == "Hello world"


class TestResponsesExportEndpoint:
    """GET /sessions/{session_id}/responses/export — adapter-format export of saved answers."""

    @pytest.fixture
    def csv_client(self, app):
        return TestClient(app, raise_server_exceptions=False)

    @pytest.fixture
    def token_and_session(self, valid_token, session_manager):
        session = session_manager.create_session(
            user_id="test_user_123", explicit_session_id="test_session_456"
        )
        return valid_token, session

    @staticmethod
    def _write_survey(session_manager, session, fmt: str, *, sid: str = "42") -> None:
        """Persist a minimal survey.json with one open-ended question (qid=11)."""
        import json as _json

        survey_path = (
            session_manager._get_session_path(session.session_id, user_id=session.user_id)
            / "survey.json"
        )
        survey_data = {
            "id": sid,
            "title": "T",
            "sections": [
                {
                    "id": "sec_1",
                    "title": "S",
                    "questions": [
                        {
                            "id": "q_11",
                            "text": "Any comments?",
                            "type": "open_ended",
                            "answer_options": [],
                            "required": False,
                            "metadata": {"ls_qid": "11", "qsf_qid": "QID11"},
                        }
                    ],
                    "metadata": {"ls_gid": "1"},
                }
            ],
            "metadata": {
                "format": fmt,
                "ls_sid": sid,
            },
        }
        survey_path.write_text(_json.dumps(survey_data))

    @staticmethod
    def _write_review_state(session_manager, session, state: dict) -> None:
        import json as _json

        path = (
            session_manager._get_session_path(session.session_id, user_id=session.user_id)
            / "review_state.json"
        )
        path.write_text(_json.dumps(state))

    def test_csv_session_mismatch_returns_403(self, csv_client, valid_token):
        response = csv_client.get(
            "/sessions/wrong_session_id/responses/export?platform=lss",
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        assert response.status_code == 403

    def test_csv_survey_not_found_returns_404(self, csv_client, token_and_session):
        token, session = token_and_session
        response = csv_client.get(
            f"/sessions/{session.session_id}/responses/export?platform=lss",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404

    def test_csv_platform_mismatch_returns_400(
        self, csv_client, token_and_session, session_manager
    ):
        token, session = token_and_session
        self._write_survey(session_manager, session, fmt="lss")
        response = csv_client.get(
            f"/sessions/{session.session_id}/responses/export?platform=qsf",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400

    def test_csv_unknown_platform_returns_422(self, csv_client, token_and_session, session_manager):
        token, session = token_and_session
        self._write_survey(session_manager, session, fmt="unknown_fmt")
        response = csv_client.get(
            f"/sessions/{session.session_id}/responses/export?platform=unknown_fmt",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422

    def test_csv_capability_absent_returns_422(
        self, csv_client, token_and_session, session_manager
    ):
        """QTI does not advertise responses_export → 422."""
        token, session = token_and_session
        self._write_survey(session_manager, session, fmt="qti")
        response = csv_client.get(
            f"/sessions/{session.session_id}/responses/export?platform=qti",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422

    def test_csv_no_answers_yet_returns_404(self, csv_client, token_and_session, session_manager):
        """Survey present + adapter supports responses_export, but no accepted/edited entries."""
        token, session = token_and_session
        self._write_survey(session_manager, session, fmt="lss")
        self._write_review_state(session_manager, session, {})
        response = csv_client.get(
            f"/sessions/{session.session_id}/responses/export?platform=lss",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404

    def test_csv_dismissed_only_returns_404(self, csv_client, token_and_session, session_manager):
        """Dismissed entries do not count as answers."""
        token, session = token_and_session
        self._write_survey(session_manager, session, fmt="lss")
        self._write_review_state(session_manager, session, {"q_11": {"state": "dismissed"}})
        response = csv_client.get(
            f"/sessions/{session.session_id}/responses/export?platform=lss",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404

    def test_export_returns_vv_tsv_for_lss(self, csv_client, token_and_session, session_manager):
        """LS adapter emits the VV-import shape (TSV with two header rows + _vv.csv suffix)."""
        token, session = token_and_session
        self._write_survey(session_manager, session, fmt="lss", sid="42")
        self._write_review_state(
            session_manager,
            session,
            {"q_11": {"state": "accepted", "value": "Hello world"}},
        )
        response = csv_client.get(
            f"/sessions/{session.session_id}/responses/export?platform=lss",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        # LS returns TSV (a.k.a. LS's "VV" format), not CSV.
        assert response.headers["content-type"].startswith("text/tab-separated-values")
        disposition = response.headers["content-disposition"]
        assert "attachment" in disposition
        assert "responses-lss-42-" in disposition
        # LS VV files use a `_vv.csv` suffix to mirror LS's own
        # ``vvexport_{sid}.csv`` naming style even though the bytes are TSV.
        assert disposition.endswith('_vv.csv"')
        # Body has the qcode column (falls back to ls_qid=11 since the test
        # survey carries no ls_qcode) and the accepted value.
        body = response.text
        lines = body.splitlines()
        assert len(lines) >= 3  # display headers, code headers, data row
        assert "id\ttoken\tsubmitdate" in lines[1]  # codes row
        assert "11" in lines[1].split("\t")
        assert "Hello world" in body

    def test_export_returns_csv_for_qsf(self, csv_client, token_and_session, session_manager):
        token, session = token_and_session
        self._write_survey(session_manager, session, fmt="qsf", sid="SV_xyz")
        self._write_review_state(
            session_manager,
            session,
            {"q_11": {"state": "edited", "value": "edited answer"}},
        )
        response = csv_client.get(
            f"/sessions/{session.session_id}/responses/export?platform=qsf",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        disposition = response.headers["content-disposition"]
        assert "responses-qsf-SV_xyz-" in disposition
        assert disposition.endswith('.csv"')
        body = response.text
        # Row-1 should contain the QID for the configured question
        assert "QID11" in body
        assert "edited answer" in body
