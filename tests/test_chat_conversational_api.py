"""Integration tests for the conversational session API (Section 4 of implement-chat-api).

Covers:
- POST/GET /chat/sessions — session lifecycle
- GET/DELETE /chat/{session_id} — session metadata and deletion
- POST /chat/{session_id}/reset — clear draft and vocab only
- POST /chat/{session_id} — chat turn (plain text + survey update)
- GET /chat/{session_id}/survey — current draft survey
- GET/PUT /chat/{session_id}/style — style profile management
- POST /chat/{session_id}/style/upload — style document upload
- POST /chat/{session_id}/upload — content document upload
- Integration scenarios: scratch-to-export, session isolation, session resume
"""

import json
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from m_shared.auth.jwt_handler import create_token
from m_shared.auth.middleware import SessionMiddleware
from m_shared.llm.tool_calling import CompletionResult, ToolCall
from m_shared.models.survey import Survey
from m_shared.session.manager import SessionManager
from shape_api.api import create_app
from shape_api.session import (
    DEFAULT_STYLE_PROFILE,
    save_draft_survey,
    save_tag_vocabulary,
)

# ---------------------------------------------------------------------------
# Reused sample payloads (mirrors test_chat_api.py)
# ---------------------------------------------------------------------------

MINIMAL_LSS = """\
<?xml version="1.0" encoding="UTF-8"?>
<document>
  <surveys><rows><row>
    <sid>42</sid>
    <surveyls_title>Test Survey</surveyls_title>
    <surveyls_description>Test description</surveyls_description>
  </row></rows></surveys>
  <groups><rows>
    <row>
      <gid>1</gid><group_name>Section One</group_name>
      <description></description><group_order>1</group_order>
    </row>
  </rows></groups>
  <questions><rows>
    <row>
      <qid>10</qid><gid>1</gid><type>T</type>
      <question>What is your name?</question><mandatory>N</mandatory>
      <question_order>1</question_order><parent_qid>0</parent_qid>
    </row>
  </rows></questions>
  <answers><rows/></answers>
</document>
"""

SAMPLE_SURVEY_DICT = {
    "id": "survey1",
    "title": "Test Survey",
    "description": "A test survey",
    "sections": [
        {
            "id": "sec1",
            "title": "Section 1",
            "description": "",
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
            "order": 0,
            "metadata": {},
        }
    ],
    "metadata": {},
}

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def jwt_secret(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("JWT_EXPIRATION_HOURS", "24")
    return "test-secret"


@pytest.fixture
def session_manager(tmp_path):
    return SessionManager(base_path=str(tmp_path / "sessions"))


@pytest.fixture
def app(session_manager, jwt_secret):
    application = create_app(session_manager=session_manager)
    application.add_middleware(SessionMiddleware, session_manager=session_manager, ttl_hours=24)
    return application


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.create_completion.return_value = "How can I help you design your survey?"

    # Chat-turn loop calls create_completion_full; mirror create_completion's
    # current return_value as text content so existing tests don't need to change.
    def _full(messages=None, tools=None, **kwargs):
        return CompletionResult(content=llm.create_completion.return_value, tool_calls=[])

    llm.create_completion_full.side_effect = _full
    return llm


@pytest.fixture
def app_with_llm(session_manager, jwt_secret, mock_llm):
    application = create_app(session_manager=session_manager, llm_client=mock_llm)
    application.add_middleware(SessionMiddleware, session_manager=session_manager, ttl_hours=24)
    return application


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def client_with_llm(app_with_llm):
    return TestClient(app_with_llm, raise_server_exceptions=False)


def _make_auth_headers(user_id: str = "test_user") -> dict:
    """Build Authorization headers for the given user_id (JWT_SECRET must be set)."""
    token = create_token(
        user_id=user_id,
        session_id="auth_session",
        org="test_org",
        roles=["user"],
    )
    return {"Authorization": f"Bearer {token}"}


def _create_chat_session(client, headers: dict) -> str:
    """Helper: POST /chat/sessions and return the new session_id."""
    resp = client.post("/chat/sessions", json={}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["session_id"]


def _text_turn(text: str) -> list:
    """One LLM round-trip: a plain text reply with no tool calls."""
    return [CompletionResult(content=text, tool_calls=[])]


def _init_survey_turn(survey_dict: dict, reply: str = "Done.") -> list:
    """Two LLM round-trips: an init_survey tool call, then a text reply."""
    return [
        CompletionResult(
            content=None,
            tool_calls=[
                ToolCall(
                    tool_call_id="c1",
                    name="init_survey",
                    arguments_json=json.dumps({"survey": survey_dict}),
                )
            ],
        ),
        CompletionResult(content=reply, tool_calls=[]),
    ]


# ---------------------------------------------------------------------------
# TestSessionLifecycle
# ---------------------------------------------------------------------------


class TestSessionLifecycle:
    def test_create_session_returns_201_with_session_id(self, client, jwt_secret):
        headers = _make_auth_headers("user1")
        resp = client.post("/chat/sessions", json={}, headers=headers)
        assert resp.status_code == 201
        data = resp.json()
        assert "session_id" in data
        assert data["user_id"] == "user1"
        assert "created_at" in data
        assert "expires_at" in data
        assert "style_profile" in data

    def test_list_sessions_returns_created_session(self, client, jwt_secret):
        headers = _make_auth_headers("user1")
        sid = _create_chat_session(client, headers)
        resp = client.get("/chat/sessions", headers=headers)
        assert resp.status_code == 200
        sessions = resp.json()["sessions"]
        session_ids = [s["session_id"] for s in sessions]
        assert sid in session_ids

    def test_get_session_metadata(self, client, jwt_secret):
        headers = _make_auth_headers("user1")
        sid = _create_chat_session(client, headers)
        resp = client.get(f"/chat/{sid}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == sid
        assert data["user_id"] == "user1"
        assert "style_profile" in data

    def test_get_foreign_session_returns_403(self, client, jwt_secret):
        headers1 = _make_auth_headers("user1")
        headers2 = _make_auth_headers("user2")
        sid = _create_chat_session(client, headers1)
        resp = client.get(f"/chat/{sid}", headers=headers2)
        assert resp.status_code == 403

    def test_delete_session_returns_200(self, client, jwt_secret):
        headers = _make_auth_headers("user1")
        sid = _create_chat_session(client, headers)
        resp = client.delete(f"/chat/{sid}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted"] is True
        assert data["session_id"] == sid
        # session should now be gone
        resp2 = client.get(f"/chat/{sid}", headers=headers)
        assert resp2.status_code == 403

    def test_reset_session_clears_draft_and_vocab_only(self, client, jwt_secret, session_manager):
        headers = _make_auth_headers("user1")
        sid = _create_chat_session(client, headers)
        base_path = str(session_manager.base_path)

        # Manually write draft and vocab
        survey = Survey(**SAMPLE_SURVEY_DICT)
        save_draft_survey(base_path, sid, survey)
        save_tag_vocabulary(base_path, sid, {"demographics": ["q1"]})

        resp = client.post(f"/chat/{sid}/reset", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["reset"] is True
        assert "draft_survey.json" in data["cleared"]
        assert "tag_vocabulary.json" in data["cleared"]

        # Confirm draft is gone
        resp2 = client.get(f"/chat/{sid}/survey", headers=headers)
        assert resp2.status_code == 200
        assert resp2.json()["survey"] is None

        # Confirm session itself still exists
        resp3 = client.get(f"/chat/{sid}", headers=headers)
        assert resp3.status_code == 200


# ---------------------------------------------------------------------------
# TestChatTurnEndpoint
# ---------------------------------------------------------------------------


class TestChatTurnEndpoint:
    def test_chat_turn_plain_text_response(self, client_with_llm, jwt_secret, mock_llm):
        headers = _make_auth_headers("user1")
        sid = _create_chat_session(client_with_llm, headers)
        mock_llm.create_completion.return_value = "Sure, I can help with that."

        resp = client_with_llm.post(
            f"/chat/{sid}",
            json={"message": "Help me design a student survey."},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "Sure, I can help with that."
        assert data["survey_updated"] is False

    def test_chat_turn_applies_mutation_via_tool(self, client_with_llm, jwt_secret, mock_llm):
        headers = _make_auth_headers("user1")
        sid = _create_chat_session(client_with_llm, headers)
        mock_llm.create_completion_full.side_effect = [
            CompletionResult(
                content=None,
                tool_calls=[
                    ToolCall(
                        tool_call_id="c1",
                        name="init_survey",
                        arguments_json=json.dumps({"survey": SAMPLE_SURVEY_DICT}),
                    )
                ],
            ),
            CompletionResult(content="Here is the new survey.", tool_calls=[]),
        ]

        resp = client_with_llm.post(
            f"/chat/{sid}",
            json={"message": "Create a basic survey."},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["survey_updated"] is True
        assert data["message"] == "Here is the new survey."

    def test_chat_turn_truncated_output_returns_clean_message(
        self, client_with_llm, jwt_secret, mock_llm
    ):
        headers = _make_auth_headers("user1")
        sid = _create_chat_session(client_with_llm, headers)
        truncated = 'Here you go.<survey_update>{"id": "survey_1", "title": "T", "sec'
        mock_llm.create_completion_full.side_effect = lambda messages=None, tools=None, **kw: (
            CompletionResult(content=truncated, tool_calls=[], finish_reason="length")
        )

        resp = client_with_llm.post(
            f"/chat/{sid}",
            json={"message": "Add 200 questions to the demographics section."},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["survey_updated"] is False
        assert "<survey_update>" not in data["message"]
        assert "too large" in data["message"].lower()

    def test_chat_turn_no_llm_returns_500(self, client, jwt_secret):
        headers = _make_auth_headers("user1")
        sid = _create_chat_session(client, headers)
        resp = client.post(
            f"/chat/{sid}",
            json={"message": "Hello"},
            headers=headers,
        )
        assert resp.status_code == 500

    def test_get_survey_after_tool_update(self, client_with_llm, jwt_secret, mock_llm):
        headers = _make_auth_headers("user1")
        sid = _create_chat_session(client_with_llm, headers)
        mock_llm.create_completion_full.side_effect = [
            CompletionResult(
                content=None,
                tool_calls=[
                    ToolCall(
                        tool_call_id="c1",
                        name="init_survey",
                        arguments_json=json.dumps({"survey": SAMPLE_SURVEY_DICT}),
                    )
                ],
            ),
            CompletionResult(content="Done.", tool_calls=[]),
        ]
        client_with_llm.post(
            f"/chat/{sid}",
            json={"message": "Create a survey."},
            headers=headers,
        )

        resp = client_with_llm.get(f"/chat/{sid}/survey", headers=headers)
        assert resp.status_code == 200
        survey = resp.json()["survey"]
        assert survey is not None
        assert survey["title"] == "Test Survey"

    def test_chat_turn_multi_tool_edit(self, client_with_llm, jwt_secret, mock_llm):
        headers = _make_auth_headers("user1")
        sid = _create_chat_session(client_with_llm, headers)
        client_with_llm.put(
            f"/chat/{sid}/survey", json={"survey": SAMPLE_SURVEY_DICT}, headers=headers
        )
        mock_llm.create_completion_full.side_effect = [
            CompletionResult(
                content=None,
                tool_calls=[
                    ToolCall(
                        tool_call_id="c1",
                        name="add_section",
                        arguments_json=json.dumps({"section": {"id": "sec2", "title": "Two"}}),
                    ),
                    ToolCall(
                        tool_call_id="c2",
                        name="add_question",
                        arguments_json=json.dumps(
                            {
                                "section_id": "sec2",
                                "question": {"id": "qa", "text": "A?", "type": "open_ended"},
                            }
                        ),
                    ),
                    ToolCall(
                        tool_call_id="c3",
                        name="add_question",
                        arguments_json=json.dumps(
                            {
                                "section_id": "sec2",
                                "question": {"id": "qb", "text": "B?", "type": "open_ended"},
                            }
                        ),
                    ),
                ],
            ),
            CompletionResult(content="Added a section with two questions.", tool_calls=[]),
        ]

        resp = client_with_llm.post(
            f"/chat/{sid}", json={"message": "add a section with 2 questions"}, headers=headers
        )
        assert resp.status_code == 200
        assert resp.json()["survey_updated"] is True
        survey = client_with_llm.get(f"/chat/{sid}/survey", headers=headers).json()["survey"]
        sec2 = next(s for s in survey["sections"] if s["id"] == "sec2")
        assert [q["id"] for q in sec2["questions"]] == ["qa", "qb"]

    def test_chat_turn_error_recovery(self, client_with_llm, jwt_secret, mock_llm):
        headers = _make_auth_headers("user1")
        sid = _create_chat_session(client_with_llm, headers)
        client_with_llm.put(
            f"/chat/{sid}/survey", json={"survey": SAMPLE_SURVEY_DICT}, headers=headers
        )
        mock_llm.create_completion_full.side_effect = [
            CompletionResult(
                content=None,
                tool_calls=[
                    ToolCall(
                        tool_call_id="c1",
                        name="update_question",
                        arguments_json=json.dumps({"question_id": "wrong", "patch": {"text": "X"}}),
                    )
                ],
            ),
            CompletionResult(
                content=None,
                tool_calls=[
                    ToolCall(
                        tool_call_id="c2",
                        name="update_question",
                        arguments_json=json.dumps(
                            {"question_id": "q1", "patch": {"text": "Fixed?"}}
                        ),
                    )
                ],
            ),
            CompletionResult(content="Fixed it.", tool_calls=[]),
        ]

        resp = client_with_llm.post(
            f"/chat/{sid}", json={"message": "reword the first question"}, headers=headers
        )
        assert resp.status_code == 200
        assert resp.json()["survey_updated"] is True
        survey = client_with_llm.get(f"/chat/{sid}/survey", headers=headers).json()["survey"]
        assert survey["sections"][0]["questions"][0]["text"] == "Fixed?"

    def test_chat_turn_move_preserves_question_id(self, client_with_llm, jwt_secret, mock_llm):
        headers = _make_auth_headers("user1")
        sid = _create_chat_session(client_with_llm, headers)
        base = {
            **SAMPLE_SURVEY_DICT,
            "sections": [
                SAMPLE_SURVEY_DICT["sections"][0],
                {
                    "id": "sec2",
                    "title": "Section 2",
                    "description": "",
                    "order": 1,
                    "metadata": {},
                    "questions": [],
                },
            ],
        }
        client_with_llm.put(f"/chat/{sid}/survey", json={"survey": base}, headers=headers)
        moved_q = SAMPLE_SURVEY_DICT["sections"][0]["questions"][0]
        mock_llm.create_completion_full.side_effect = [
            CompletionResult(
                content=None,
                tool_calls=[
                    ToolCall(
                        tool_call_id="c1",
                        name="delete_question",
                        arguments_json=json.dumps({"question_id": "q1"}),
                    ),
                    ToolCall(
                        tool_call_id="c2",
                        name="add_question",
                        arguments_json=json.dumps({"section_id": "sec2", "question": moved_q}),
                    ),
                ],
            ),
            CompletionResult(content="Moved it.", tool_calls=[]),
        ]

        resp = client_with_llm.post(
            f"/chat/{sid}", json={"message": "move q1 to section 2"}, headers=headers
        )
        assert resp.status_code == 200
        assert resp.json()["survey_updated"] is True
        survey = client_with_llm.get(f"/chat/{sid}/survey", headers=headers).json()["survey"]
        sec1 = next(s for s in survey["sections"] if s["id"] == "sec1")
        sec2 = next(s for s in survey["sections"] if s["id"] == "sec2")
        assert [q["id"] for q in sec1["questions"]] == []
        assert [q["id"] for q in sec2["questions"]] == ["q1"]

    def test_get_survey_no_draft_returns_null(self, client, jwt_secret):
        headers = _make_auth_headers("user1")
        sid = _create_chat_session(client, headers)
        resp = client.get(f"/chat/{sid}/survey", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["survey"] is None


# ---------------------------------------------------------------------------
# TestSurveyUpdateEndpoint
# ---------------------------------------------------------------------------


class TestSurveyUpdateEndpoint:
    def test_put_survey_saves_draft(self, client, jwt_secret):
        headers = _make_auth_headers("user1")
        sid = _create_chat_session(client, headers)
        resp = client.put(
            f"/chat/{sid}/survey", json={"survey": SAMPLE_SURVEY_DICT}, headers=headers
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "saved"
        get_resp = client.get(f"/chat/{sid}/survey", headers=headers)
        assert get_resp.json()["survey"]["title"] == "Test Survey"

    def test_put_survey_returns_validation_issues(self, client, jwt_secret):
        survey = {
            **SAMPLE_SURVEY_DICT,
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
                            "text": "Pick one",
                            "type": "single_choice",
                            "order": 0,
                            "required": False,
                            "min_value": None,
                            "max_value": None,
                            "step": None,
                            "metadata": {},
                            "answer_options": [
                                {"id": "opt1", "text": "Yes"},
                                {"id": "opt2", "text": "No"},
                            ],
                        }
                    ],
                }
            ],
        }
        headers = _make_auth_headers("user1")
        sid = _create_chat_session(client, headers)
        resp = client.put(f"/chat/{sid}/survey", json={"survey": survey}, headers=headers)
        assert resp.status_code == 200
        issues = resp.json()["validation_issues"]
        assert any(i["code"] == "scale_too_short" for i in issues)

    def test_put_survey_rejects_invalid_schema(self, client, jwt_secret):
        headers = _make_auth_headers("user1")
        sid = _create_chat_session(client, headers)
        resp = client.put(f"/chat/{sid}/survey", json={"survey": {"bad": "data"}}, headers=headers)
        assert resp.status_code == 422

    def test_put_survey_wrong_session_returns_403(self, client, jwt_secret):
        headers_a = _make_auth_headers("user_a")
        headers_b = _make_auth_headers("user_b")
        sid = _create_chat_session(client, headers_a)
        resp = client.put(
            f"/chat/{sid}/survey", json={"survey": SAMPLE_SURVEY_DICT}, headers=headers_b
        )
        assert resp.status_code == 403

    def test_put_survey_no_prior_draft(self, client, jwt_secret):
        headers = _make_auth_headers("user1")
        sid = _create_chat_session(client, headers)
        get_resp = client.get(f"/chat/{sid}/survey", headers=headers)
        assert get_resp.json()["survey"] is None
        resp = client.put(
            f"/chat/{sid}/survey", json={"survey": SAMPLE_SURVEY_DICT}, headers=headers
        )
        assert resp.status_code == 200
        get_resp = client.get(f"/chat/{sid}/survey", headers=headers)
        assert get_resp.json()["survey"] is not None


# ---------------------------------------------------------------------------
# TestSurveyMutationEndpoints
# ---------------------------------------------------------------------------

_NEW_SECTION = {"id": "sec2", "title": "Section 2"}
_NEW_QUESTION = {"id": "q2", "text": "New question?", "type": "open_ended"}


class TestSurveyMutationEndpoints:
    def _seed(self, client, headers) -> str:
        sid = _create_chat_session(client, headers)
        client.put(f"/chat/{sid}/survey", json={"survey": SAMPLE_SURVEY_DICT}, headers=headers)
        return sid

    def test_add_section(self, client, jwt_secret):
        headers = _make_auth_headers("user1")
        sid = self._seed(client, headers)
        resp = client.post(
            f"/chat/{sid}/survey/sections", json={"section": _NEW_SECTION}, headers=headers
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "saved"
        survey = client.get(f"/chat/{sid}/survey", headers=headers).json()["survey"]
        assert [s["id"] for s in survey["sections"]] == ["sec1", "sec2"]

    def test_update_section(self, client, jwt_secret):
        headers = _make_auth_headers("user1")
        sid = self._seed(client, headers)
        resp = client.patch(
            f"/chat/{sid}/survey/sections/sec1", json={"title": "Renamed"}, headers=headers
        )
        assert resp.status_code == 200
        survey = client.get(f"/chat/{sid}/survey", headers=headers).json()["survey"]
        assert survey["sections"][0]["title"] == "Renamed"

    def test_delete_section(self, client, jwt_secret):
        headers = _make_auth_headers("user1")
        sid = self._seed(client, headers)
        resp = client.delete(f"/chat/{sid}/survey/sections/sec1", headers=headers)
        assert resp.status_code == 200
        survey = client.get(f"/chat/{sid}/survey", headers=headers).json()["survey"]
        assert survey["sections"] == []

    def test_add_question(self, client, jwt_secret):
        headers = _make_auth_headers("user1")
        sid = self._seed(client, headers)
        resp = client.post(
            f"/chat/{sid}/survey/sections/sec1/questions",
            json={"question": _NEW_QUESTION},
            headers=headers,
        )
        assert resp.status_code == 200
        survey = client.get(f"/chat/{sid}/survey", headers=headers).json()["survey"]
        assert [q["id"] for q in survey["sections"][0]["questions"]] == ["q1", "q2"]

    def test_update_question(self, client, jwt_secret):
        headers = _make_auth_headers("user1")
        sid = self._seed(client, headers)
        resp = client.patch(
            f"/chat/{sid}/survey/questions/q1", json={"text": "Changed?"}, headers=headers
        )
        assert resp.status_code == 200
        survey = client.get(f"/chat/{sid}/survey", headers=headers).json()["survey"]
        assert survey["sections"][0]["questions"][0]["text"] == "Changed?"

    def test_delete_question(self, client, jwt_secret):
        headers = _make_auth_headers("user1")
        sid = self._seed(client, headers)
        resp = client.delete(f"/chat/{sid}/survey/questions/q1", headers=headers)
        assert resp.status_code == 200
        survey = client.get(f"/chat/{sid}/survey", headers=headers).json()["survey"]
        assert survey["sections"][0]["questions"] == []

    def test_add_question_unknown_section_returns_404(self, client, jwt_secret):
        headers = _make_auth_headers("user1")
        sid = self._seed(client, headers)
        resp = client.post(
            f"/chat/{sid}/survey/sections/nope/questions",
            json={"question": _NEW_QUESTION},
            headers=headers,
        )
        assert resp.status_code == 404

    def test_patch_unknown_question_returns_404(self, client, jwt_secret):
        headers = _make_auth_headers("user1")
        sid = self._seed(client, headers)
        resp = client.patch(
            f"/chat/{sid}/survey/questions/nope", json={"text": "x"}, headers=headers
        )
        assert resp.status_code == 404

    def test_duplicate_section_returns_409(self, client, jwt_secret):
        headers = _make_auth_headers("user1")
        sid = self._seed(client, headers)
        resp = client.post(
            f"/chat/{sid}/survey/sections",
            json={"section": {"id": "sec1", "title": "Dup"}},
            headers=headers,
        )
        assert resp.status_code == 409

    def test_mutation_wrong_session_returns_403(self, client, jwt_secret):
        headers_a = _make_auth_headers("user_a")
        headers_b = _make_auth_headers("user_b")
        sid = self._seed(client, headers_a)
        resp = client.delete(f"/chat/{sid}/survey/sections/sec1", headers=headers_b)
        assert resp.status_code == 403

    def test_mutation_unauthenticated_returns_401(self, client, jwt_secret):
        resp = client.delete("/chat/any_session/survey/sections/sec1")
        assert resp.status_code == 401

    def test_end_to_end_edit_sequence(self, client, jwt_secret):
        headers = _make_auth_headers("user1")
        sid = self._seed(client, headers)
        client.post(f"/chat/{sid}/survey/sections", json={"section": _NEW_SECTION}, headers=headers)
        client.post(
            f"/chat/{sid}/survey/sections/sec2/questions",
            json={"question": {"id": "qX", "text": "Original?", "type": "open_ended"}},
            headers=headers,
        )
        client.patch(f"/chat/{sid}/survey/questions/qX", json={"text": "Final?"}, headers=headers)
        survey = client.get(f"/chat/{sid}/survey", headers=headers).json()["survey"]
        sec2 = next(s for s in survey["sections"] if s["id"] == "sec2")
        assert sec2["questions"][0]["text"] == "Final?"

    def test_move_section(self, client, jwt_secret):
        headers = _make_auth_headers("user1")
        sid = self._seed(client, headers)
        client.post(f"/chat/{sid}/survey/sections", json={"section": _NEW_SECTION}, headers=headers)
        resp = client.patch(
            f"/chat/{sid}/survey/sections/sec1/position",
            json={"after_id": "sec2"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        survey = client.get(f"/chat/{sid}/survey", headers=headers).json()["survey"]
        assert [s["id"] for s in survey["sections"]] == ["sec2", "sec1"]

    def test_move_question_within_section(self, client, jwt_secret):
        headers = _make_auth_headers("user1")
        sid = self._seed(client, headers)
        client.post(
            f"/chat/{sid}/survey/sections/sec1/questions",
            json={"question": _NEW_QUESTION},
            headers=headers,
        )
        resp = client.patch(
            f"/chat/{sid}/survey/questions/q1/position", json={"after_id": "q2"}, headers=headers
        )
        assert resp.status_code == 200
        survey = client.get(f"/chat/{sid}/survey", headers=headers).json()["survey"]
        assert [q["id"] for q in survey["sections"][0]["questions"]] == ["q2", "q1"]

    def test_move_question_to_other_section(self, client, jwt_secret):
        headers = _make_auth_headers("user1")
        sid = self._seed(client, headers)
        client.post(f"/chat/{sid}/survey/sections", json={"section": _NEW_SECTION}, headers=headers)
        resp = client.patch(
            f"/chat/{sid}/survey/questions/q1/position",
            json={"section_id": "sec2"},
            headers=headers,
        )
        assert resp.status_code == 200
        survey = client.get(f"/chat/{sid}/survey", headers=headers).json()["survey"]
        assert survey["sections"][0]["questions"] == []
        assert [q["id"] for q in survey["sections"][1]["questions"]] == ["q1"]

    def test_move_unknown_section_returns_404(self, client, jwt_secret):
        headers = _make_auth_headers("user1")
        sid = self._seed(client, headers)
        resp = client.patch(f"/chat/{sid}/survey/sections/nope/position", json={}, headers=headers)
        assert resp.status_code == 404

    def test_move_unknown_question_returns_404(self, client, jwt_secret):
        headers = _make_auth_headers("user1")
        sid = self._seed(client, headers)
        resp = client.patch(f"/chat/{sid}/survey/questions/nope/position", json={}, headers=headers)
        assert resp.status_code == 404

    def test_move_question_unauthenticated_returns_401(self, client, jwt_secret):
        resp = client.patch("/chat/any_session/survey/questions/q1/position", json={})
        assert resp.status_code == 401

    def test_move_wrong_session_returns_403(self, client, jwt_secret):
        headers_a = _make_auth_headers("user_a")
        headers_b = _make_auth_headers("user_b")
        sid = self._seed(client, headers_a)
        resp = client.patch(f"/chat/{sid}/survey/questions/q1/position", json={}, headers=headers_b)
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# TestStyleEndpoints
# ---------------------------------------------------------------------------


class TestStyleEndpoints:
    def test_get_style_returns_defaults(self, client, jwt_secret):
        headers = _make_auth_headers("user1")
        sid = _create_chat_session(client, headers)
        resp = client.get(f"/chat/{sid}/style", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == sid
        assert data["style_profile"]["language"] == DEFAULT_STYLE_PROFILE["language"]

    def test_put_style_updates_language(self, client, jwt_secret):
        headers = _make_auth_headers("user1")
        sid = _create_chat_session(client, headers)
        resp = client.put(
            f"/chat/{sid}/style",
            json={"language": "nl"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["style_profile"]["language"] == "nl"

    def test_put_style_partial_update_preserves_other_fields(self, client, jwt_secret):
        headers = _make_auth_headers("user1")
        sid = _create_chat_session(client, headers)
        # First set language
        client.put(f"/chat/{sid}/style", json={"language": "fr"}, headers=headers)
        # Then set free_text only
        resp = client.put(
            f"/chat/{sid}/style",
            json={"free_text": "Use formal tone."},
            headers=headers,
        )
        assert resp.status_code == 200
        profile = resp.json()["style_profile"]
        assert profile["language"] == "fr"
        assert profile["free_text"] == "Use formal tone."

    def test_style_upload_updates_document_summary(self, client, jwt_secret):
        headers = _make_auth_headers("user1")
        sid = _create_chat_session(client, headers)

        with patch(
            "shape_api.routes.chat.extract_style_document", return_value="Use short sentences."
        ):
            resp = client.post(
                f"/chat/{sid}/style/upload",
                files={"file": ("style_guide.txt", BytesIO(b"Use short sentences."), "text/plain")},
                headers=headers,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["filename"] == "style_guide.txt"
        assert data["characters_extracted"] == len("Use short sentences.")

        # Verify it was saved in the style profile
        resp2 = client.get(f"/chat/{sid}/style", headers=headers)
        assert resp2.status_code == 200
        assert "Use short sentences." in resp2.json()["style_profile"]["document_summary"]


# ---------------------------------------------------------------------------
# TestDocumentUpload
# ---------------------------------------------------------------------------


class TestDocumentUpload:
    def test_upload_txt_returns_topic_summary(self, client, jwt_secret):
        headers = _make_auth_headers("user1")
        sid = _create_chat_session(client, headers)
        extracted_text = "This document covers student wellbeing metrics."

        with patch("shape_api.routes.chat.document_to_markdown", return_value=extracted_text):
            resp = client.post(
                f"/chat/{sid}/upload",
                files={"file": ("data.txt", BytesIO(b"raw content"), "text/plain")},
                headers=headers,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["filename"] == "data.txt"
        assert data["characters_extracted"] == len(extracted_text)
        # No LLM → fallback summary is first 200 chars of extracted
        assert data["topic_summary"] == extracted_text[:200]

    def test_upload_unsupported_type_returns_422(self, client, jwt_secret):
        headers = _make_auth_headers("user1")
        sid = _create_chat_session(client, headers)
        resp = client.post(
            f"/chat/{sid}/upload",
            files={"file": ("data.csv", BytesIO(b"a,b,c"), "text/csv")},
            headers=headers,
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# TestScenarioIntegration
# ---------------------------------------------------------------------------


class TestScenarioIntegration:
    def test_scenario_scratch_to_export(self, client_with_llm, jwt_secret, mock_llm):
        """Create session → plain chat → survey-update chat → GET survey → export."""
        headers = _make_auth_headers("user1")
        sid = _create_chat_session(client_with_llm, headers)

        # Turn 1: plain text response
        mock_llm.create_completion_full.side_effect = _text_turn("Let's start with the basics.")
        r1 = client_with_llm.post(
            f"/chat/{sid}",
            json={"message": "I need a wellbeing survey."},
            headers=headers,
        )
        assert r1.status_code == 200
        assert r1.json()["survey_updated"] is False

        # Turn 2: survey created via init_survey tool
        mock_llm.create_completion_full.side_effect = _init_survey_turn(
            SAMPLE_SURVEY_DICT, "Here's a draft."
        )
        r2 = client_with_llm.post(
            f"/chat/{sid}",
            json={"message": "Create the survey now."},
            headers=headers,
        )
        assert r2.status_code == 200
        assert r2.json()["survey_updated"] is True

        # GET survey
        r3 = client_with_llm.get(f"/chat/{sid}/survey", headers=headers)
        assert r3.status_code == 200
        survey = r3.json()["survey"]
        assert survey is not None
        assert survey["title"] == "Test Survey"

        # Export to LimeSurvey
        r4 = client_with_llm.post(
            "/export",
            json={"format": "limesurvey", "survey": survey},
            headers=headers,
        )
        assert r4.status_code == 200
        assert "<document>" in r4.json()["content"]

    def test_scenario_session_isolation(self, client, jwt_secret):
        """User1's session must be invisible and inaccessible to user2."""
        h1 = _make_auth_headers("user1")
        h2 = _make_auth_headers("user2")

        sid1 = _create_chat_session(client, h1)

        # user2 cannot GET user1's session
        assert client.get(f"/chat/{sid1}", headers=h2).status_code == 403
        # user2 cannot DELETE user1's session
        assert client.delete(f"/chat/{sid1}", headers=h2).status_code == 403
        # user2 cannot POST to user1's session
        assert client.post(f"/chat/{sid1}/reset", headers=h2).status_code == 403

        # user2's session list does not include user1's session
        r = client.get("/chat/sessions", headers=h2)
        assert r.status_code == 200
        ids = [s["session_id"] for s in r.json()["sessions"]]
        assert sid1 not in ids

        # user1's session list does include sid1
        r2 = client.get("/chat/sessions", headers=h1)
        assert r2.status_code == 200
        ids2 = [s["session_id"] for s in r2.json()["sessions"]]
        assert sid1 in ids2

    def test_scenario_upload_propose_refine_create(self, client_with_llm, jwt_secret, mock_llm):
        """Upload content doc → LLM proposes structure → refine → create on platform."""
        headers = _make_auth_headers("user1")
        sid = _create_chat_session(client_with_llm, headers)

        # Step 1: Upload content doc — LLM called for topic summary
        mock_llm.create_completion.return_value = "Employee satisfaction survey topics"
        with patch(
            "shape_api.routes.chat.document_to_markdown",
            return_value="Employee satisfaction content for survey design.",
        ):
            r_upload = client_with_llm.post(
                f"/chat/{sid}/upload",
                files={"file": ("content.txt", b"raw content", "text/plain")},
                headers=headers,
            )
        assert r_upload.status_code == 200, r_upload.text
        upload_data = r_upload.json()
        assert upload_data["filename"] == "content.txt"
        assert upload_data["topic_summary"]

        # Step 2: Plain chat turn — structure proposal without survey update
        mock_llm.create_completion_full.side_effect = _text_turn(
            "Sure, let me propose a structure for you."
        )
        r2 = client_with_llm.post(
            f"/chat/{sid}",
            json={"message": "Can you propose a survey structure?"},
            headers=headers,
        )
        assert r2.status_code == 200
        assert r2.json()["survey_updated"] is False

        # Step 3: Chat turn creates the survey via init_survey
        mock_llm.create_completion_full.side_effect = _init_survey_turn(
            SAMPLE_SURVEY_DICT, "Here is a draft."
        )
        r3 = client_with_llm.post(
            f"/chat/{sid}",
            json={"message": "Please create the survey now."},
            headers=headers,
        )
        assert r3.status_code == 200
        assert r3.json()["survey_updated"] is True

        # Step 4: Refine the title via update_section's sibling — re-init with new title
        refined = {**SAMPLE_SURVEY_DICT, "title": "Employee Satisfaction Survey"}
        mock_llm.create_completion_full.side_effect = _init_survey_turn(refined, "Refined!")
        r4 = client_with_llm.post(
            f"/chat/{sid}",
            json={"message": "Change the title to Employee Satisfaction Survey."},
            headers=headers,
        )
        assert r4.status_code == 200
        assert r4.json()["survey_updated"] is True

        # Step 5: GET survey — confirm refined title persisted
        r5 = client_with_llm.get(f"/chat/{sid}/survey", headers=headers)
        assert r5.status_code == 200
        survey = r5.json()["survey"]
        assert survey["title"] == "Employee Satisfaction Survey"

        # Step 6: POST /create with QTI (file_export path, no credentials needed)
        r6 = client_with_llm.post(
            "/create",
            json={"format": "qti", "survey": survey},
            headers=headers,
        )
        assert r6.status_code == 200
        data = r6.json()
        assert data["created_via"] == "file_export"
        assert "<assessmentTest" in data["platform_id"]

    def test_scenario_import_validate_improve_export(
        self, client_with_llm, jwt_secret, mock_llm, session_manager
    ):
        """Import existing survey → validate → improve via chat → export."""
        headers = _make_auth_headers("user_c")

        # Step 1: Import from LimeSurvey format
        r_import = client_with_llm.post(
            "/import",
            json={"format": "limesurvey", "content": MINIMAL_LSS},
            headers=headers,
        )
        assert r_import.status_code == 200, r_import.text
        imported_survey = r_import.json()["survey"]

        # Step 2: Create chat session
        sid = _create_chat_session(client_with_llm, headers)

        # Step 3: Seed session draft directly
        save_draft_survey(
            str(session_manager.base_path),
            sid,
            Survey(**imported_survey),
        )

        # Step 4: Validate via session_id — mock LLM returns empty issues list
        mock_llm.create_completion.return_value = "[]"
        r_validate = client_with_llm.post(
            "/validate",
            json={"session_id": sid},
            headers=headers,
        )
        assert r_validate.status_code == 200, r_validate.text
        assert isinstance(r_validate.json()["issues"], list)

        # Step 5: Chat turn to improve survey via init_survey
        improved = {**SAMPLE_SURVEY_DICT, "title": "Improved Test Survey"}
        mock_llm.create_completion_full.side_effect = _init_survey_turn(improved, "Improved.")
        r_chat = client_with_llm.post(
            f"/chat/{sid}",
            json={"message": "Improve the survey title."},
            headers=headers,
        )
        assert r_chat.status_code == 200
        assert r_chat.json()["survey_updated"] is True

        # Step 6: GET survey — confirm improved title
        r_survey = client_with_llm.get(f"/chat/{sid}/survey", headers=headers)
        assert r_survey.status_code == 200
        survey = r_survey.json()["survey"]
        assert survey["title"] == "Improved Test Survey"

        # Step 7: Export back to LimeSurvey
        r_export = client_with_llm.post(
            "/export",
            json={"format": "limesurvey", "survey": survey},
            headers=headers,
        )
        assert r_export.status_code == 200
        assert "<document>" in r_export.json()["content"]

    def test_scenario_session_resume(self, app, jwt_secret, mock_llm, session_manager):
        """Session state (conversation + draft) persists across client instances."""
        headers = _make_auth_headers("user1")

        # Client A: create session and send a message
        mock_llm.create_completion.return_value = "Hello!"
        app_with_llm = create_app(session_manager=session_manager, llm_client=mock_llm)
        app_with_llm.add_middleware(
            SessionMiddleware, session_manager=session_manager, ttl_hours=24
        )
        client_a = TestClient(app_with_llm, raise_server_exceptions=False)
        sid = _create_chat_session(client_a, headers)

        mock_llm.create_completion_full.side_effect = _init_survey_turn(
            SAMPLE_SURVEY_DICT, "Here it is."
        )
        client_a.post(f"/chat/{sid}", json={"message": "Create a survey."}, headers=headers)

        # Client B: new TestClient, same session_manager (same tmp_path)
        app_b = create_app(session_manager=session_manager)
        app_b.add_middleware(SessionMiddleware, session_manager=session_manager, ttl_hours=24)
        client_b = TestClient(app_b, raise_server_exceptions=False)

        # Session metadata is still accessible
        r_meta = client_b.get(f"/chat/{sid}", headers=headers)
        assert r_meta.status_code == 200
        assert r_meta.json()["session_id"] == sid

        # Draft survey persists
        r_survey = client_b.get(f"/chat/{sid}/survey", headers=headers)
        assert r_survey.status_code == 200
        assert r_survey.json()["survey"] is not None
        assert r_survey.json()["survey"]["title"] == "Test Survey"


# ---------------------------------------------------------------------------
# TestMethodologicalAdvisor
# ---------------------------------------------------------------------------

_SD_SURVEY_DICT = {
    "id": "s1",
    "title": "Conduct Survey",
    "description": "",
    "metadata": {},
    "sections": [
        {
            "id": "sec1",
            "title": "Section",
            "description": "",
            "order": 0,
            "metadata": {},
            "questions": [
                {
                    "id": "q1",
                    "text": "Do you always follow the code of conduct?",
                    "type": "open_ended",
                    "answer_options": [],
                    "order": 0,
                    "required": True,
                    "min_value": None,
                    "max_value": None,
                    "step": None,
                    "metadata": {},
                }
            ],
        }
    ],
}


class TestMethodologicalAdvisor:
    def test_advisory_note_appears_when_new_issue_introduced(
        self, client_with_llm, jwt_secret, mock_llm
    ):
        headers = _make_auth_headers("user1")
        sid = _create_chat_session(client_with_llm, headers)

        mock_llm.create_completion_full.side_effect = _init_survey_turn(
            _SD_SURVEY_DICT, "Here is the updated survey."
        )

        resp = client_with_llm.post(
            f"/chat/{sid}",
            json={"message": "Add a conduct question."},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["survey_updated"] is True
        assert "was this intentional?" in data["message"]

    def test_preexisting_issue_not_resurfaced(
        self, client_with_llm, jwt_secret, mock_llm, session_manager
    ):
        headers = _make_auth_headers("user1")
        sid = _create_chat_session(client_with_llm, headers)

        # Seed the draft with the SD survey so the issue already exists in baseline
        save_draft_survey(str(session_manager.base_path), sid, Survey(**_SD_SURVEY_DICT))

        # Re-apply the same survey: survey_updated is True but no NEW issue is introduced
        mock_llm.create_completion_full.side_effect = _init_survey_turn(
            _SD_SURVEY_DICT, "No changes."
        )

        resp = client_with_llm.post(
            f"/chat/{sid}",
            json={"message": "Review the survey."},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["survey_updated"] is True
        assert "was this intentional?" not in data["message"]
