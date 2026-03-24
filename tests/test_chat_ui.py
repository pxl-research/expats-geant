"""Tests for shape_ui: api_client unit tests and router integration tests.

Unit tests for api_client:
- create_session success / API error
- list_sessions returns session list
- get_session success / 403
- send_message success / API error
- get_survey success / null survey
- get_style / update_style
- upload_style_doc / upload_content_doc
- export_survey / create_survey_on_platform
- reset_session / delete_session

Integration tests for router:
- GET / redirects to /auth/login when no cookie
- GET / returns 200 with sessions when authenticated
- POST /sessions creates session and redirects
- GET /session/{id}/setup renders setup page
- POST /session/{id}/setup saves style and redirects
- POST /session/{id}/setup/style-doc (HTMX) uploads doc and returns partial
- GET /session/{id}/chat renders chat page
- POST /session/{id}/chat (HTMX) sends message and returns partial
- GET /session/{id}/export renders export page
- POST /session/{id}/reset redirects to chat
- DELETE /session/{id} redirects to home
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from shape_ui.api_client import (
    APIError,
    create_session,
    create_survey_on_platform,
    delete_session,
    export_survey,
    get_session,
    get_style,
    get_survey,
    list_sessions,
    reset_session,
    send_message,
    update_style,
    upload_content_doc,
    upload_style_doc,
)
from shape_ui.main import create_app

BASE = "http://localhost:8003"
TOKEN = "test-jwt-token"
SESSION_ID = "test-session-uuid-1234"

SAMPLE_SESSION = {
    "session_id": SESSION_ID,
    "user_id": "user1",
    "created_at": "2026-01-01T12:00:00",
    "expires_at": "2026-01-02T12:00:00",
    "style_profile": {"language": "en", "free_text": "", "document_summary": None},
}

SAMPLE_SURVEY = {
    "id": "survey1",
    "title": "My Survey",
    "description": "A test",
    "sections": [
        {
            "id": "sec1",
            "title": "Section 1",
            "description": "",
            "order": 0,
            "metadata": {},
            "questions": [
                {
                    "id": "q1",
                    "text": "How are you?",
                    "type": "open_ended",
                    "order": 0,
                    "answer_options": [],
                    "required": False,
                    "min_value": None,
                    "max_value": None,
                    "step": None,
                    "metadata": {},
                }
            ],
        }
    ],
    "metadata": {},
}


# ---------------------------------------------------------------------------
# api_client unit tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_create_session_success():
    respx.post(f"{BASE}/chat/sessions").mock(return_value=httpx.Response(201, json=SAMPLE_SESSION))
    result = await create_session(TOKEN)
    assert result["session_id"] == SESSION_ID


@pytest.mark.asyncio
@respx.mock
async def test_create_session_api_error():
    respx.post(f"{BASE}/chat/sessions").mock(
        return_value=httpx.Response(401, json={"detail": "Unauthorized"})
    )
    with pytest.raises(APIError) as exc_info:
        await create_session(TOKEN)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
@respx.mock
async def test_list_sessions_returns_list():
    respx.get(f"{BASE}/chat/sessions").mock(
        return_value=httpx.Response(200, json={"sessions": [SAMPLE_SESSION]})
    )
    sessions = await list_sessions(TOKEN)
    assert isinstance(sessions, list)
    assert len(sessions) == 1
    assert sessions[0]["session_id"] == SESSION_ID


@pytest.mark.asyncio
@respx.mock
async def test_list_sessions_empty():
    respx.get(f"{BASE}/chat/sessions").mock(return_value=httpx.Response(200, json={"sessions": []}))
    sessions = await list_sessions(TOKEN)
    assert sessions == []


@pytest.mark.asyncio
@respx.mock
async def test_get_session_success():
    respx.get(f"{BASE}/chat/{SESSION_ID}").mock(
        return_value=httpx.Response(200, json=SAMPLE_SESSION)
    )
    result = await get_session(TOKEN, SESSION_ID)
    assert result["session_id"] == SESSION_ID


@pytest.mark.asyncio
@respx.mock
async def test_get_session_forbidden():
    respx.get(f"{BASE}/chat/{SESSION_ID}").mock(
        return_value=httpx.Response(403, json={"detail": "Access denied"})
    )
    with pytest.raises(APIError) as exc_info:
        await get_session(TOKEN, SESSION_ID)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
@respx.mock
async def test_send_message_success():
    respx.post(f"{BASE}/chat/{SESSION_ID}").mock(
        return_value=httpx.Response(
            200, json={"message": "Hello! I can help.", "survey_updated": False}
        )
    )
    result = await send_message(TOKEN, SESSION_ID, "Hello")
    assert result["message"] == "Hello! I can help."
    assert result["survey_updated"] is False


@pytest.mark.asyncio
@respx.mock
async def test_send_message_survey_updated():
    respx.post(f"{BASE}/chat/{SESSION_ID}").mock(
        return_value=httpx.Response(
            200, json={"message": "Updated your survey.", "survey_updated": True}
        )
    )
    result = await send_message(TOKEN, SESSION_ID, "Add a question about age")
    assert result["survey_updated"] is True


@pytest.mark.asyncio
@respx.mock
async def test_get_survey_success():
    respx.get(f"{BASE}/chat/{SESSION_ID}/survey").mock(
        return_value=httpx.Response(200, json={"survey": SAMPLE_SURVEY})
    )
    survey = await get_survey(TOKEN, SESSION_ID)
    assert survey is not None
    assert survey["title"] == "My Survey"


@pytest.mark.asyncio
@respx.mock
async def test_get_survey_null():
    respx.get(f"{BASE}/chat/{SESSION_ID}/survey").mock(
        return_value=httpx.Response(200, json={"survey": None})
    )
    survey = await get_survey(TOKEN, SESSION_ID)
    assert survey is None


@pytest.mark.asyncio
@respx.mock
async def test_get_style_success():
    respx.get(f"{BASE}/chat/{SESSION_ID}/style").mock(
        return_value=httpx.Response(
            200,
            json={
                "session_id": SESSION_ID,
                "style_profile": {
                    "language": "nl",
                    "free_text": "Formal",
                    "document_summary": None,
                },
            },
        )
    )
    style = await get_style(TOKEN, SESSION_ID)
    assert style["language"] == "nl"


@pytest.mark.asyncio
@respx.mock
async def test_update_style_success():
    respx.put(f"{BASE}/chat/{SESSION_ID}/style").mock(
        return_value=httpx.Response(
            200,
            json={
                "session_id": SESSION_ID,
                "style_profile": {
                    "language": "fr",
                    "free_text": "New rules",
                    "document_summary": None,
                },
            },
        )
    )
    style = await update_style(TOKEN, SESSION_ID, "fr", "New rules")
    assert style["language"] == "fr"


@pytest.mark.asyncio
@respx.mock
async def test_upload_style_doc_success():
    respx.post(f"{BASE}/chat/{SESSION_ID}/style/upload").mock(
        return_value=httpx.Response(
            200,
            json={
                "filename": "guide.pdf",
                "topic_summary": "Academic writing norms",
                "characters_extracted": 1500,
            },
        )
    )
    result = await upload_style_doc(TOKEN, SESSION_ID, b"PDF bytes", "guide.pdf")
    assert result["filename"] == "guide.pdf"
    assert result["characters_extracted"] == 1500


@pytest.mark.asyncio
@respx.mock
async def test_upload_content_doc_success():
    respx.post(f"{BASE}/chat/{SESSION_ID}/upload").mock(
        return_value=httpx.Response(
            200,
            json={
                "filename": "context.docx",
                "topic_summary": "Survey background info",
                "characters_extracted": 800,
            },
        )
    )
    result = await upload_content_doc(TOKEN, SESSION_ID, b"DOCX bytes", "context.docx")
    assert result["topic_summary"] == "Survey background info"


@pytest.mark.asyncio
@respx.mock
async def test_export_survey_success():
    respx.get(f"{BASE}/chat/{SESSION_ID}/survey").mock(
        return_value=httpx.Response(200, json={"survey": SAMPLE_SURVEY})
    )
    respx.post(f"{BASE}/export").mock(
        return_value=httpx.Response(200, json={"format": "lss", "content": "<survey/>"})
    )
    result = await export_survey(TOKEN, SESSION_ID, "lss")
    assert result["content"] == "<survey/>"


@pytest.mark.asyncio
@respx.mock
async def test_export_survey_no_draft_raises():
    respx.get(f"{BASE}/chat/{SESSION_ID}/survey").mock(
        return_value=httpx.Response(200, json={"survey": None})
    )
    with pytest.raises(APIError) as exc_info:
        await export_survey(TOKEN, SESSION_ID, "lss")
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
@respx.mock
async def test_create_survey_on_platform_file_export():
    respx.get(f"{BASE}/chat/{SESSION_ID}/survey").mock(
        return_value=httpx.Response(200, json={"survey": SAMPLE_SURVEY})
    )
    respx.post(f"{BASE}/create").mock(
        return_value=httpx.Response(
            200,
            json={"format": "qsf", "platform_id": "LS_12345", "created_via": "file_export"},
        )
    )
    result = await create_survey_on_platform(TOKEN, SESSION_ID, "qsf")
    assert result["created_via"] == "file_export"


@pytest.mark.asyncio
@respx.mock
async def test_reset_session_success():
    respx.post(f"{BASE}/chat/{SESSION_ID}/reset").mock(
        return_value=httpx.Response(
            200,
            json={"reset": True, "session_id": SESSION_ID, "cleared": ["draft_survey.json"]},
        )
    )
    result = await reset_session(TOKEN, SESSION_ID)
    assert result["reset"] is True


@pytest.mark.asyncio
@respx.mock
async def test_delete_session_success():
    respx.delete(f"{BASE}/chat/{SESSION_ID}").mock(
        return_value=httpx.Response(200, json={"deleted": True, "session_id": SESSION_ID})
    )
    result = await delete_session(TOKEN, SESSION_ID)
    assert result["deleted"] is True


# ---------------------------------------------------------------------------
# Router integration tests
# ---------------------------------------------------------------------------


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=False)


COOKIE = {"chat_token": TOKEN}


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


def test_index_no_cookie_redirects_to_login(client):
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["location"]


@respx.mock
def test_index_with_cookie_lists_sessions(client):
    respx.get(f"{BASE}/chat/sessions").mock(
        return_value=httpx.Response(200, json={"sessions": [SAMPLE_SESSION]})
    )
    resp = client.get("/", cookies=COOKIE)
    assert resp.status_code == 200
    assert SESSION_ID[:8] in resp.text


@respx.mock
def test_index_empty_sessions(client):
    respx.get(f"{BASE}/chat/sessions").mock(return_value=httpx.Response(200, json={"sessions": []}))
    resp = client.get("/", cookies=COOKIE)
    assert resp.status_code == 200
    assert "No sessions" in resp.text


@respx.mock
def test_create_session_redirects_to_setup(client):
    respx.post(f"{BASE}/chat/sessions").mock(return_value=httpx.Response(201, json=SAMPLE_SESSION))
    resp = client.post("/sessions", cookies=COOKIE, follow_redirects=False)
    assert resp.status_code == 302
    assert f"/session/{SESSION_ID}/setup" in resp.headers["location"]


def test_create_session_no_cookie_redirects_to_login(client):
    resp = client.post("/sessions", follow_redirects=False)
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["location"]


@respx.mock
def test_setup_page_renders(client):
    respx.get(f"{BASE}/chat/{SESSION_ID}/style").mock(
        return_value=httpx.Response(
            200,
            json={
                "session_id": SESSION_ID,
                "style_profile": {"language": "en", "free_text": "", "document_summary": None},
            },
        )
    )
    resp = client.get(f"/session/{SESSION_ID}/setup", cookies=COOKIE)
    assert resp.status_code == 200
    assert "Configure" in resp.text


@respx.mock
def test_setup_submit_redirects_to_chat(client):
    respx.put(f"{BASE}/chat/{SESSION_ID}/style").mock(
        return_value=httpx.Response(
            200,
            json={
                "session_id": SESSION_ID,
                "style_profile": {"language": "nl", "free_text": "Formal"},
            },
        )
    )
    resp = client.post(
        f"/session/{SESSION_ID}/setup",
        data={"language": "nl", "free_text": "Formal"},
        cookies=COOKIE,
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert f"/session/{SESSION_ID}/chat" in resp.headers["location"]


@respx.mock
def test_style_doc_upload_returns_partial(client):
    respx.post(f"{BASE}/chat/{SESSION_ID}/style/upload").mock(
        return_value=httpx.Response(
            200,
            json={
                "filename": "guide.pdf",
                "topic_summary": "Writing norms",
                "characters_extracted": 400,
            },
        )
    )
    resp = client.post(
        f"/session/{SESSION_ID}/setup/style-doc",
        files={"file": ("guide.pdf", b"bytes", "application/pdf")},
        cookies=COOKIE,
    )
    assert resp.status_code == 200
    assert "guide.pdf" in resp.text


@respx.mock
def test_chat_page_renders(client):
    respx.get(f"{BASE}/chat/{SESSION_ID}").mock(
        return_value=httpx.Response(200, json=SAMPLE_SESSION)
    )
    respx.get(f"{BASE}/chat/{SESSION_ID}/style").mock(
        return_value=httpx.Response(
            200,
            json={"session_id": SESSION_ID, "style_profile": {"language": "en"}},
        )
    )
    respx.get(f"{BASE}/chat/{SESSION_ID}/survey").mock(
        return_value=httpx.Response(200, json={"survey": None})
    )
    respx.get(f"{BASE}/chat/{SESSION_ID}/messages").mock(
        return_value=httpx.Response(200, json={"messages": []})
    )
    resp = client.get(f"/session/{SESSION_ID}/chat", cookies=COOKIE)
    assert resp.status_code == 200
    assert "chat" in resp.text.lower()


@respx.mock
def test_chat_send_returns_message_partial(client):
    respx.post(f"{BASE}/chat/{SESSION_ID}").mock(
        return_value=httpx.Response(200, json={"message": "Great idea!", "survey_updated": False})
    )
    resp = client.post(
        f"/session/{SESSION_ID}/chat",
        data={"message": "Add a question about location"},
        cookies=COOKIE,
    )
    assert resp.status_code == 200
    assert "Great idea!" in resp.text


@respx.mock
def test_chat_send_with_survey_update(client):
    respx.post(f"{BASE}/chat/{SESSION_ID}").mock(
        return_value=httpx.Response(200, json={"message": "Updated!", "survey_updated": True})
    )
    respx.get(f"{BASE}/chat/{SESSION_ID}/survey").mock(
        return_value=httpx.Response(200, json={"survey": SAMPLE_SURVEY})
    )
    resp = client.post(
        f"/session/{SESSION_ID}/chat",
        data={"message": "Add a section"},
        cookies=COOKIE,
    )
    assert resp.status_code == 200
    assert "Updated" in resp.text


@respx.mock
def test_export_page_renders(client):
    respx.get(f"{BASE}/chat/{SESSION_ID}/survey").mock(
        return_value=httpx.Response(200, json={"survey": SAMPLE_SURVEY})
    )
    resp = client.get(f"/session/{SESSION_ID}/export", cookies=COOKIE)
    assert resp.status_code == 200
    assert "Export" in resp.text
    assert "LimeSurvey" in resp.text


@respx.mock
def test_export_push_shows_cleanup_modal(client):
    respx.get(f"{BASE}/chat/{SESSION_ID}/survey").mock(
        return_value=httpx.Response(200, json={"survey": SAMPLE_SURVEY})
    )
    respx.post(f"{BASE}/create").mock(
        return_value=httpx.Response(200, json={"platform_id": "123", "created_via": "api"})
    )
    resp = client.post(
        f"/session/{SESSION_ID}/export",
        data={"action": "push", "fmt": "lss"},
        cookies=COOKIE,
        headers={"HX-Request": "true"},
    )
    assert resp.status_code == 200
    assert "cleanup-modal" in resp.text
    assert "Delete session data" in resp.text


@respx.mock
def test_export_download_shows_cleanup_modal(client):
    respx.get(f"{BASE}/chat/{SESSION_ID}/survey").mock(
        return_value=httpx.Response(200, json={"survey": SAMPLE_SURVEY})
    )
    respx.post(f"{BASE}/export").mock(
        return_value=httpx.Response(200, json={"content": "<xml/>", "filename": "survey.lss"})
    )
    resp = client.post(
        f"/session/{SESSION_ID}/export",
        data={"action": "download", "fmt": "lss"},
        cookies=COOKIE,
        headers={"HX-Request": "true"},
    )
    assert resp.status_code == 200
    assert "cleanup-modal" in resp.text
    assert "Delete session data" in resp.text


@respx.mock
def test_reset_session_redirects(client):
    respx.post(f"{BASE}/chat/{SESSION_ID}/reset").mock(
        return_value=httpx.Response(
            200,
            json={"reset": True, "session_id": SESSION_ID, "cleared": []},
        )
    )
    resp = client.post(f"/session/{SESSION_ID}/reset", cookies=COOKIE, follow_redirects=False)
    assert resp.status_code == 302
    assert f"/session/{SESSION_ID}/chat" in resp.headers["location"]


@respx.mock
def test_delete_session_redirects_to_home(client):
    respx.delete(f"{BASE}/chat/{SESSION_ID}").mock(
        return_value=httpx.Response(200, json={"deleted": True, "session_id": SESSION_ID})
    )
    resp = client.delete(f"/session/{SESSION_ID}", cookies=COOKIE, follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/"


def test_auth_login_redirects(client):
    resp = client.get("/auth/login", follow_redirects=False)
    assert resp.status_code in (302, 307)
    # Redirects to shape-api public URL
    assert "auth/login" in resp.headers["location"]


@patch(
    "shape_ui.router.get_logout_url", new_callable=AsyncMock, return_value="http://keycloak/logout"
)
def test_auth_logout_clears_cookie(mock_logout_url, client):
    resp = client.get("/auth/logout", cookies=COOKIE, follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "http://keycloak/logout"
    # Cookie should be cleared
    set_cookie = resp.headers.get("set-cookie", "")
    assert "chat_token" in set_cookie


def test_auth_callback_no_params_returns_error(client):
    resp = client.get("/auth/callback")
    assert resp.status_code == 400
    assert "failed" in resp.text.lower()


def test_auth_callback_direct_token(client):
    resp = client.get("/auth/callback?token=mytoken", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/"
    assert "chat_token" in resp.headers.get("set-cookie", "")
