"""Tagging engine: suggests and normalises question tags via LLM."""

import json
import logging

from m_shared.llm.client import LLMClient
from m_shared.models.question import Question


def normalise_tag(tag: str) -> str:
    """Normalise a tag to lowercase, stripped, with spaces replaced by dashes."""
    return tag.lower().strip().replace(" ", "-")


def _parse_tags(raw: str) -> list[str]:
    """Parse LLM response into a list of tag strings, with fallback."""
    text = raw.strip()

    if text.startswith("```"):
        lines = text.splitlines()
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[1:end]).strip()

    try:
        data = json.loads(text)
        if isinstance(data, list):
            return [str(t) for t in data if t]
    except (json.JSONDecodeError, ValueError):
        pass

    logging.warning("LLM tag response was not valid JSON; returning empty list")
    return []


def suggest_tags(
    question: Question,
    llm_client: LLMClient,
    vocabulary: dict[str, list[str]] | None = None,
    style_profile: dict | None = None,
) -> list[str]:
    """Suggest normalised tags for a question.

    Args:
        question: Question to tag
        llm_client: Initialised LLM client
        vocabulary: Existing tag vocabulary {tag: [question_id, ...]}; encourages reuse
        style_profile: Optional style profile (used for language hint)

    Returns:
        List of normalised tag strings
    """
    lang = "English"
    if style_profile:
        from m_chat.style import _LANGUAGE_NAMES

        lang_code = style_profile.get("language", "en")
        lang = _LANGUAGE_NAMES.get(lang_code, lang_code)

    instruction_parts = [f"Language: {lang}."]

    if vocabulary:
        existing = ", ".join(sorted(vocabulary.keys()))
        instruction_parts.append(
            f"Existing tags already used in this survey: {existing}. "
            "Prefer reusing existing tags where appropriate."
        )

    instruction_parts.append(
        "Suggest 2–5 tags for the following question. Return a JSON array of strings."
    )

    system_msg = "\n".join(instruction_parts)
    user_msg = f"<question>{question.text}</question>\nType: {question.type.value}"

    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]
    raw = llm_client.create_completion(messages=messages)
    tags = _parse_tags(raw)
    return [normalise_tag(t) for t in tags]
