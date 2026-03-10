"""Tests for m_chat.session — file I/O helpers."""

from m_chat.session import (
    DEFAULT_STYLE_PROFILE,
    append_message,
    get_session_path,
    load_conversation,
    load_draft_survey,
    load_style_profile,
    load_tag_vocabulary,
    save_draft_survey,
    save_style_profile,
    save_tag_vocabulary,
    update_vocabulary,
)
from m_shared.models.answer_option import AnswerOption
from m_shared.models.question import Question, QuestionType
from m_shared.models.section import Section
from m_shared.models.survey import Survey
from m_shared.session import SessionManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_survey(survey_id: str = "s1") -> Survey:
    return Survey(
        id=survey_id,
        title="Test Survey",
        sections=[
            Section(
                id="sec1",
                title="Section 1",
                questions=[
                    Question(
                        id="q1",
                        text="How satisfied are you?",
                        type=QuestionType.SINGLE_CHOICE,
                        answer_options=[
                            AnswerOption(id="a1", text="Yes"),
                            AnswerOption(id="a2", text="No"),
                            AnswerOption(id="a3", text="Maybe"),
                            AnswerOption(id="a4", text="Unsure"),
                        ],
                    )
                ],
            )
        ],
    )


# ---------------------------------------------------------------------------
# get_session_path
# ---------------------------------------------------------------------------


def test_get_session_path_returns_correct_path(tmp_path):
    p = get_session_path(str(tmp_path), "abc123")
    assert p == tmp_path / "abc123"


# ---------------------------------------------------------------------------
# Draft survey round-trip
# ---------------------------------------------------------------------------


def test_load_draft_survey_missing_returns_none(tmp_path):
    session_id = "sess1"
    (tmp_path / session_id).mkdir()
    assert load_draft_survey(str(tmp_path), session_id) is None


def test_save_and_load_draft_survey(tmp_path):
    session_id = "sess1"
    (tmp_path / session_id).mkdir()
    survey = _make_survey()
    save_draft_survey(str(tmp_path), session_id, survey)
    loaded = load_draft_survey(str(tmp_path), session_id)
    assert loaded is not None
    assert loaded.id == survey.id
    assert loaded.title == survey.title


def test_save_draft_survey_creates_parent_dirs(tmp_path):
    session_id = "new_session"
    survey = _make_survey()
    save_draft_survey(str(tmp_path), session_id, survey)
    assert (tmp_path / session_id / "draft_survey.json").exists()


def test_save_and_load_draft_survey_preserves_sections(tmp_path):
    session_id = "sess2"
    survey = _make_survey()
    save_draft_survey(str(tmp_path), session_id, survey)
    loaded = load_draft_survey(str(tmp_path), session_id)
    assert len(loaded.sections) == 1
    assert loaded.sections[0].questions[0].id == "q1"


# ---------------------------------------------------------------------------
# Tag vocabulary round-trip
# ---------------------------------------------------------------------------


def test_load_tag_vocabulary_missing_returns_empty(tmp_path):
    session_id = "sess1"
    (tmp_path / session_id).mkdir()
    assert load_tag_vocabulary(str(tmp_path), session_id) == {}


def test_save_and_load_tag_vocabulary(tmp_path):
    session_id = "sess1"
    (tmp_path / session_id).mkdir()
    vocab = {"demographics": ["q1", "q2"], "satisfaction": ["q3"]}
    save_tag_vocabulary(str(tmp_path), session_id, vocab)
    loaded = load_tag_vocabulary(str(tmp_path), session_id)
    assert loaded == vocab


def test_save_tag_vocabulary_creates_parent_dirs(tmp_path):
    session_id = "new_session"
    save_tag_vocabulary(str(tmp_path), session_id, {"tag": ["q1"]})
    assert (tmp_path / session_id / "tag_vocabulary.json").exists()


# ---------------------------------------------------------------------------
# update_vocabulary
# ---------------------------------------------------------------------------


def test_update_vocabulary_adds_new_tag(tmp_path):
    vocab = {}
    result = update_vocabulary(vocab, ["demographics"], "q1")
    assert "demographics" in result
    assert "q1" in result["demographics"]


def test_update_vocabulary_normalises_tags():
    vocab = {}
    result = update_vocabulary(vocab, ["Work Life"], "q1")
    assert "work-life" in result


def test_update_vocabulary_appends_question_id():
    vocab = {"demographics": ["q1"]}
    result = update_vocabulary(vocab, ["demographics"], "q2")
    assert "q1" in result["demographics"]
    assert "q2" in result["demographics"]


def test_update_vocabulary_no_duplicate_question_id():
    vocab = {"demographics": ["q1"]}
    result = update_vocabulary(vocab, ["demographics"], "q1")
    assert result["demographics"].count("q1") == 1


def test_update_vocabulary_multiple_tags():
    vocab = {}
    result = update_vocabulary(vocab, ["age", "gender", "location"], "q1")
    assert len(result) == 3
    for tag in ("age", "gender", "location"):
        assert "q1" in result[tag]


def test_update_vocabulary_preserves_existing_tags():
    vocab = {"existing": ["q0"]}
    result = update_vocabulary(vocab, ["new-tag"], "q1")
    assert "existing" in result
    assert result["existing"] == ["q0"]


# ---------------------------------------------------------------------------
# Conversation helpers
# ---------------------------------------------------------------------------


def test_load_conversation_missing_returns_empty(tmp_path):
    session_id = "sess1"
    (tmp_path / session_id).mkdir()
    assert load_conversation(str(tmp_path), session_id) == []


def test_append_message_creates_file(tmp_path):
    session_id = "sess1"
    append_message(str(tmp_path), session_id, "user", "Hello")
    messages = load_conversation(str(tmp_path), session_id)
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "Hello"


def test_append_message_multiple(tmp_path):
    session_id = "sess1"
    append_message(str(tmp_path), session_id, "user", "Hello")
    append_message(str(tmp_path), session_id, "assistant", "Hi there!")
    messages = load_conversation(str(tmp_path), session_id)
    assert len(messages) == 2
    assert messages[1]["role"] == "assistant"


def test_append_message_has_timestamp(tmp_path):
    session_id = "sess1"
    append_message(str(tmp_path), session_id, "user", "msg")
    messages = load_conversation(str(tmp_path), session_id)
    assert "timestamp" in messages[0]


# ---------------------------------------------------------------------------
# Style profile
# ---------------------------------------------------------------------------


def test_load_style_profile_missing_returns_default(tmp_path):
    session_id = "sess1"
    (tmp_path / session_id).mkdir()
    profile = load_style_profile(str(tmp_path), session_id)
    assert profile == DEFAULT_STYLE_PROFILE


def test_save_and_load_style_profile(tmp_path):
    session_id = "sess1"
    (tmp_path / session_id).mkdir()
    profile = {
        "language": "nl",
        "free_text": "formal",
        "document_summary": "...",
        "defaults_applied": False,
    }
    save_style_profile(str(tmp_path), session_id, profile)
    loaded = load_style_profile(str(tmp_path), session_id)
    assert loaded == profile


def test_default_style_profile_is_correct():
    assert DEFAULT_STYLE_PROFILE["language"] == "en"
    assert DEFAULT_STYLE_PROFILE["defaults_applied"] is True
    assert "free_text" in DEFAULT_STYLE_PROFILE
    assert "document_summary" in DEFAULT_STYLE_PROFILE


def test_save_style_profile_creates_parent_dirs(tmp_path):
    session_id = "new_session"
    save_style_profile(str(tmp_path), session_id, {"language": "fr"})
    assert (tmp_path / session_id / "style_profile.json").exists()


# ---------------------------------------------------------------------------
# list_sessions_for_user
# ---------------------------------------------------------------------------


def test_list_sessions_for_user_filters_by_user(tmp_path):
    manager = SessionManager(base_path=str(tmp_path))
    manager.create_session(
        user_id="alice", jwt_token="token-alice", explicit_session_id="sess-alice-1"
    )
    manager.create_session(
        user_id="alice", jwt_token="token-alice-2", explicit_session_id="sess-alice-2"
    )
    manager.create_session(user_id="bob", jwt_token="token-bob", explicit_session_id="sess-bob-1")

    alice_sessions = manager.list_sessions_for_user("alice")
    bob_sessions = manager.list_sessions_for_user("bob")

    assert len(alice_sessions) == 2
    assert len(bob_sessions) == 1
    assert all(s.user_id == "alice" for s in alice_sessions)


def test_list_sessions_for_user_returns_empty_for_unknown(tmp_path):
    manager = SessionManager(base_path=str(tmp_path))
    manager.create_session(user_id="alice", jwt_token="token-alice")
    result = manager.list_sessions_for_user("unknown")
    assert result == []


# ---------------------------------------------------------------------------
# Multi-session isolation
# ---------------------------------------------------------------------------


def test_two_sessions_dont_interfere(tmp_path):
    survey_a = _make_survey("survey-a")
    survey_b = _make_survey("survey-b")

    save_draft_survey(str(tmp_path), "session-a", survey_a)
    save_draft_survey(str(tmp_path), "session-b", survey_b)

    loaded_a = load_draft_survey(str(tmp_path), "session-a")
    loaded_b = load_draft_survey(str(tmp_path), "session-b")

    assert loaded_a.id == "survey-a"
    assert loaded_b.id == "survey-b"


def test_explicit_session_id_allows_multi_session(tmp_path):
    manager = SessionManager(base_path=str(tmp_path))
    s1 = manager.create_session(
        user_id="user1", jwt_token="same-token", explicit_session_id="uuid-001"
    )
    s2 = manager.create_session(
        user_id="user1", jwt_token="same-token", explicit_session_id="uuid-002"
    )

    assert s1.session_id == "uuid-001"
    assert s2.session_id == "uuid-002"
    assert s1.session_id != s2.session_id


def test_jwt_hash_still_works_without_explicit_id(tmp_path):
    manager = SessionManager(base_path=str(tmp_path))
    s1 = manager.create_session(user_id="user1", jwt_token="my-token")
    s2 = manager.create_session(user_id="user1", jwt_token="my-token")
    assert s1.session_id == s2.session_id
