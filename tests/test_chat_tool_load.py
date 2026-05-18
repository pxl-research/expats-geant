"""Integration tests for the chat-turn tool-call loop (get_full_survey).

Covers:
- happy path (tool call → text update saved)
- pure Q&A (no tool, no update)
- soft enforcement: <survey_update> without prior tool call still applied + warning
- loop cap on runaway tool calls
- clobber reproducer: PUT a survey, chat-turn copies it verbatim, edits survive
"""

import json
import logging
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from m_shared.auth.jwt_handler import create_token
from m_shared.auth.middleware import SessionMiddleware
from m_shared.llm.tool_calling import CompletionResult, ToolCall
from m_shared.models.survey import Survey
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


class TestToolCallLoopHappyPath:
    def test_tool_call_then_survey_update_saves_draft(self, session_manager, jwt_secret, caplog):
        llm = MagicMock()
        update_payload = json.dumps(_SURVEY)
        llm.create_completion_full.side_effect = [
            CompletionResult(content=None, tool_calls=[_tool_call()]),
            CompletionResult(
                content=f"Done! <survey_update>{update_payload}</survey_update>",
                tool_calls=[],
            ),
        ]
        client = _make_client(session_manager, llm)
        h = _auth_headers()
        sid = _new_session(client, h)

        with caplog.at_level(logging.INFO, logger="shape_api.conversation"):
            r = client.post(
                f"/chat/{sid}",
                json={"message": "please add a question about colours"},
                headers=h,
            )

        assert r.status_code == 200
        assert r.json()["survey_updated"] is True
        assert llm.create_completion_full.call_count == 2

        r = client.get(f"/chat/{sid}/survey", headers=h)
        assert r.json()["survey"]["sections"][0]["questions"][0]["text"].startswith(
            "What is your favourite colour"
        )

        assert any(
            "get_full_survey" in rec.message for rec in caplog.records
        ), "expected INFO log for the tool call"


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


class TestSoftEnforcement:
    def test_survey_update_without_prior_tool_call_still_applied_with_warning(
        self, session_manager, jwt_secret, caplog
    ):
        llm = MagicMock()
        update_payload = json.dumps(_SURVEY)
        llm.create_completion_full.side_effect = [
            CompletionResult(
                content=f"Sure! <survey_update>{update_payload}</survey_update>",
                tool_calls=[],
            )
        ]
        client = _make_client(session_manager, llm)
        h = _auth_headers()
        sid = _new_session(client, h)

        with caplog.at_level(logging.WARNING, logger="shape_api.conversation"):
            r = client.post(f"/chat/{sid}", json={"message": "rewrite it"}, headers=h)

        assert r.status_code == 200
        assert r.json()["survey_updated"] is True
        assert any("survey_update_without_tool_load" in rec.message for rec in caplog.records)


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


class TestClobberReproducer:
    def test_carefully_crafted_answer_options_survive_round_trip(self, session_manager, jwt_secret):
        """The original bug: a user PUTs a survey with curated option text,
        then asks a question in chat. With the tool-loaded approach, the LLM
        can copy the JSON verbatim and the edits survive."""
        llm = MagicMock()
        client = _make_client(session_manager, llm)
        h = _auth_headers()
        sid = _new_session(client, h)

        # 1. User PUTs the survey
        r = client.put(f"/chat/{sid}/survey", json={"survey": _SURVEY}, headers=h)
        assert r.status_code == 200

        # 2. Simulate a chat turn where the LLM dutifully loads the survey
        # and emits a <survey_update> that mirrors the tool result back verbatim.
        # The mock's create_completion_full needs to:
        #   - return a tool call on call 1
        #   - return the tool-result JSON wrapped in <survey_update> on call 2
        # We achieve that by capturing what gets appended to the messages list
        # (the tool result) and feeding it back as the second response.
        call_count = {"n": 0}
        captured = {"tool_result": None}

        def _full(messages=None, tools=None, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return CompletionResult(content=None, tool_calls=[_tool_call()])
            # Find the latest role=tool message in `messages`
            for m in reversed(messages):
                if m.get("role") == "tool":
                    captured["tool_result"] = m["content"]
                    break
            payload = captured["tool_result"]
            return CompletionResult(
                content=f"Updated. <survey_update>{payload}</survey_update>",
                tool_calls=[],
            )

        llm.create_completion_full.side_effect = _full

        # 3. Send a chat message that triggers the tool-load + update
        r = client.post(
            f"/chat/{sid}",
            json={"message": "what do you think of this survey?"},
            headers=h,
        )
        assert r.status_code == 200
        assert r.json()["survey_updated"] is True

        # 4. The carefully-crafted EPC label must survive
        r = client.get(f"/chat/{sid}/survey", headers=h)
        got = r.json()["survey"]
        opt_texts = [o["text"] for o in got["sections"][0]["questions"][0]["answer_options"]]
        assert "EPC label" in opt_texts
        assert opt_texts == ["Red", "Blue", "EPC label"]
        # Round-trip should be exact for every option
        assert Survey(**got).model_dump() == Survey(**_SURVEY).model_dump()
