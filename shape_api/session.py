"""Shape session data helpers — pure file I/O, no business logic."""

import json
from datetime import UTC, datetime
from pathlib import Path

from m_shared.models.survey import Survey

DEFAULT_STYLE_PROFILE: dict = {
    "language": "en",
    "free_text": "",
    "document_summary": "",
    "defaults_applied": True,
}


def get_session_path(base_path: str, session_id: str) -> Path:
    """Return the Path to the session directory.

    Searches the nested user-scoped layout (base_path/{user_hash}/{session_id})
    first, then falls back to flat layout (base_path/{session_id}).
    """
    base = Path(base_path)
    if not base.exists():
        return base / session_id
    for user_dir in base.iterdir():
        if not user_dir.is_dir():
            continue
        candidate = user_dir / session_id
        if candidate.exists():
            return candidate
    return base / session_id


# ---------------------------------------------------------------------------
# Draft survey
# ---------------------------------------------------------------------------


def load_draft_survey(base_path: str, session_id: str) -> Survey | None:
    """Load the draft survey from the session, or None if not present."""
    path = get_session_path(base_path, session_id) / "draft_survey.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return Survey(**data)


def save_draft_survey(base_path: str, session_id: str, survey: Survey) -> None:
    """Persist the draft survey to the session directory."""
    path = get_session_path(base_path, session_id) / "draft_survey.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(survey.model_dump_json(indent=2))


# ---------------------------------------------------------------------------
# Tag vocabulary
# ---------------------------------------------------------------------------


def load_tag_vocabulary(base_path: str, session_id: str) -> dict[str, list[str]]:
    """Load tag vocabulary from the session, or empty dict if not present."""
    path = get_session_path(base_path, session_id) / "tag_vocabulary.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def save_tag_vocabulary(base_path: str, session_id: str, vocab: dict) -> None:
    """Persist the tag vocabulary to the session directory."""
    path = get_session_path(base_path, session_id) / "tag_vocabulary.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(vocab, indent=2))


def update_vocabulary(vocab: dict, new_tags: list[str], question_id: str) -> dict:
    """Add new_tags to vocab, mapping each to question_id.

    Tags are normalised before insertion. Existing question mappings for a tag
    are preserved; question_id is appended if not already present.

    Args:
        vocab: Existing vocabulary dict {tag: [question_id, ...]}
        new_tags: Tags to add (will be normalised)
        question_id: Question to associate with these tags

    Returns:
        Updated vocabulary dict
    """
    from shape_api.tagging_engine import normalise_tag

    updated = dict(vocab)
    for raw_tag in new_tags:
        tag = normalise_tag(raw_tag)
        if tag not in updated:
            updated[tag] = []
        if question_id not in updated[tag]:
            updated[tag].append(question_id)
    return updated


# ---------------------------------------------------------------------------
# Conversation
# ---------------------------------------------------------------------------


def load_conversation(base_path: str, session_id: str) -> list[dict]:
    """Load the conversation history from the session, or empty list."""
    path = get_session_path(base_path, session_id) / "conversation.json"
    if not path.exists():
        return []
    return json.loads(path.read_text())


def append_message(base_path: str, session_id: str, role: str, content: str) -> None:
    """Append a message to the conversation log."""
    messages = load_conversation(base_path, session_id)
    messages.append(
        {
            "role": role,
            "content": content,
            "timestamp": datetime.now(tz=UTC).isoformat(),
        }
    )
    path = get_session_path(base_path, session_id) / "conversation.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(messages, indent=2))


# ---------------------------------------------------------------------------
# Style profile
# ---------------------------------------------------------------------------


def load_style_profile(base_path: str, session_id: str) -> dict:
    """Load style profile from the session, or DEFAULT_STYLE_PROFILE if not present."""
    path = get_session_path(base_path, session_id) / "style_profile.json"
    if not path.exists():
        return dict(DEFAULT_STYLE_PROFILE)
    return json.loads(path.read_text())


def save_style_profile(base_path: str, session_id: str, profile: dict) -> None:
    """Persist the style profile to the session directory."""
    path = get_session_path(base_path, session_id) / "style_profile.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile, indent=2))


def load_documents_context(base_path: str, session_id: str) -> str:
    """Concatenate all extracted .md files from uploads/ for LLM context."""
    uploads = get_session_path(base_path, session_id) / "uploads"
    if not uploads.exists():
        return ""
    parts = []
    for md_file in sorted(uploads.glob("*.md")):
        parts.append(f"--- Document: {md_file.stem} ---\n{md_file.read_text()}")
    return "\n\n".join(parts)


def clear_draft_and_vocabulary(base_path: str, session_id: str) -> None:
    """Delete draft_survey.json and tag_vocabulary.json; leave all else intact."""
    session_path = get_session_path(base_path, session_id)
    for filename in ("draft_survey.json", "tag_vocabulary.json"):
        f = session_path / filename
        if f.exists():
            f.unlink()


def initialize_chat_session(base_path: str, session_id: str) -> None:
    """Write default style profile, empty vocabulary, empty conversation, and style_documents dir."""
    save_style_profile(base_path, session_id, dict(DEFAULT_STYLE_PROFILE))
    save_tag_vocabulary(base_path, session_id, {})
    session_path = get_session_path(base_path, session_id)
    (session_path / "conversation.json").write_text("[]")
    (session_path / "style_documents").mkdir(exist_ok=True)
