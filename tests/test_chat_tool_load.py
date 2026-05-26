"""Integration tests for the chat-turn tool-call loop (granular mutations).

Covers:
- happy path (get_full_survey then a mutation tool saves the draft)
- pure Q&A (no tool, no update)
- loop cap on runaway tool calls
- no-clobber: an unrelated edit leaves carefully-crafted fields byte-identical
"""

import json
import logging
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from m_shared.auth.jwt_handler import create_token
from m_shared.auth.middleware import SessionMiddleware
from m_shared.llm.tool_calling import CompletionResult, ToolCall
from m_shared.session.manager import SessionManager
from shape_api.api import create_app
from shape_api.conversation import MAX_TOOL_CALL_ITERATIONS

_SURVEY = {
    "id": "s1",
    "title": "Test Survey",
    "description": "",
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
                    "text": "What is your favourite colour?",
                    "type": "single_choice",
                    "order": 0,
                    "required": True,
                    "min_value": None,
                    "max_value": None,
                    "step": None,
                    "metadata": {},
                    "answer_options": [
                        {"id": "opt_red", "text": "Red", "value": None},
                        {"id": "opt_blue", "text": "Blue", "value": None},
                        {"id": "opt_carefully_curated", "text": "EPC label", "value": None},
                    ],
                }
            ],
        }
    ],
    "metadata": {},
}


@pytest.fixture
def jwt_secret(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-which-is-long-enough-32b")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("JWT_EXPIRATION_HOURS", "24")
    return "test-secret-key-which-is-long-enough-32b"


@pytest.fixture
def session_manager(tmp_path):
    return SessionManager(base_path=str(tmp_path / "sessions"))


def _make_client(session_manager, llm):
    app = create_app(session_manager=session_manager, llm_client=llm)
    app.add_middleware(SessionMiddleware, session_manager=session_manager, ttl_hours=24)
    return TestClient(app, raise_server_exceptions=False)


def _auth_headers(user_id="alice"):
    tok = create_token(user_id=user_id, session_id="auth_session", org="acme", roles=["user"])
    return {"Authorization": f"Bearer {tok}"}


def _new_session(client, headers):
    r = client.post("/chat/sessions", json={}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["session_id"]


def _tool_call(name="get_full_survey", arguments_json="{}", call_id="call_1"):
    return ToolCall(tool_call_id=call_id, name=name, arguments_json=arguments_json)


# ---------------------------------------------------------------------------


def _add_question_call(section_id, question, call_id="call_2"):
    return _tool_call(
        name="add_question",
        arguments_json=json.dumps({"section_id": section_id, "question": question}),
        call_id=call_id,
    )


class TestToolCallLoopHappyPath:
    def test_get_full_then_mutation_saves_draft(self, session_manager, jwt_secret):
        llm = MagicMock()
        client = _make_client(session_manager, llm)
        h = _auth_headers()
        sid = _new_session(client, h)
        client.put(f"/chat/{sid}/survey", json={"survey": _SURVEY}, headers=h)

        new_q = {"id": "q2", "text": "Any other thoughts?", "type": "open_ended"}
        llm.create_completion_full.side_effect = [
            CompletionResult(content=None, tool_calls=[_tool_call()]),
            CompletionResult(content=None, tool_calls=[_add_question_call("sec1", new_q)]),
            CompletionResult(content="Added the question.", tool_calls=[]),
        ]

        r = client.post(
            f"/chat/{sid}",
            json={"message": "please add a free-text question"},
            headers=h,
        )

        assert r.status_code == 200
        assert r.json()["survey_updated"] is True
        assert llm.create_completion_full.call_count == 3

        r = client.get(f"/chat/{sid}/survey", headers=h)
        qids = [q["id"] for q in r.json()["survey"]["sections"][0]["questions"]]
        assert qids == ["q1", "q2"]


class TestPureQAndATurn:
    def test_text_only_response_no_tool_no_save(self, session_manager, jwt_secret):
        llm = MagicMock()
        llm.create_completion_full.side_effect = [
            CompletionResult(content="Hi there!", tool_calls=[])
        ]
        client = _make_client(session_manager, llm)
        h = _auth_headers()
        sid = _new_session(client, h)

        r = client.post(f"/chat/{sid}", json={"message": "hello"}, headers=h)

        assert r.status_code == 200
        data = r.json()
        assert data["survey_updated"] is False
        assert data["message"] == "Hi there!"
        assert llm.create_completion_full.call_count == 1


class TestLoopCap:
    def test_runaway_tool_calls_hit_cap_and_return_gracefully(
        self, session_manager, jwt_secret, caplog
    ):
        llm = MagicMock()
        llm.create_completion_full.side_effect = [
            CompletionResult(content=None, tool_calls=[_tool_call(call_id=f"c{i}")])
            for i in range(MAX_TOOL_CALL_ITERATIONS + 2)
        ]
        client = _make_client(session_manager, llm)
        h = _auth_headers()
        sid = _new_session(client, h)

        with caplog.at_level(logging.WARNING, logger="shape_api.conversation"):
            r = client.post(f"/chat/{sid}", json={"message": "spin forever"}, headers=h)

        assert r.status_code == 200
        assert r.json()["survey_updated"] is False
        # The model is asked at most MAX_TOOL_CALL_ITERATIONS times
        assert llm.create_completion_full.call_count == MAX_TOOL_CALL_ITERATIONS
        assert any("tool_loop_cap_hit" in rec.message for rec in caplog.records)
        # Fallback text returned to the user
        assert "tool-call budget" in r.json()["message"]


class TestNoClobber:
    def test_unrelated_edit_leaves_curated_fields_byte_identical(self, session_manager, jwt_secret):
        """With granular mutations, a chat turn that edits one thing cannot
        clobber unrelated fields: untouched questions are never re-serialised
        by the model, so carefully-crafted option text survives verbatim."""
        llm = MagicMock()
        client = _make_client(session_manager, llm)
        h = _auth_headers()
        sid = _new_session(client, h)

        # 1. User PUTs the survey with curated answer-option text
        r = client.put(f"/chat/{sid}/survey", json={"survey": _SURVEY}, headers=h)
        assert r.status_code == 200

        # 2. Chat turn renames the section only — q1's options are never touched
        llm.create_completion_full.side_effect = [
            CompletionResult(
                content=None,
                tool_calls=[
                    _tool_call(
                        name="update_section",
                        arguments_json=json.dumps(
                            {"section_id": "sec1", "patch": {"title": "Preferences"}}
                        ),
                    )
                ],
            ),
            CompletionResult(content="Renamed the section.", tool_calls=[]),
        ]
        r = client.post(
            f"/chat/{sid}",
            json={"message": "rename section 1 to Preferences"},
            headers=h,
        )
        assert r.status_code == 200
        assert r.json()["survey_updated"] is True

        # 3. The carefully-crafted EPC label must survive untouched
        got = client.get(f"/chat/{sid}/survey", headers=h).json()["survey"]
        assert got["sections"][0]["title"] == "Preferences"
        opt_texts = [o["text"] for o in got["sections"][0]["questions"][0]["answer_options"]]
        assert opt_texts == ["Red", "Blue", "EPC label"]
