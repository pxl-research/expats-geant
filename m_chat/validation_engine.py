"""Validation engine: deterministic and LLM-assisted survey quality checks."""

import json
import logging
from dataclasses import dataclass
from typing import Literal

from m_shared.llm.client import LLMClient
from m_shared.models.question import Question, QuestionType
from m_shared.models.survey import Survey

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class ValidationIssue:
    """A single validation finding for a question."""

    question_id: str
    severity: Literal["error", "warning", "info"]
    code: str
    message: str


# ---------------------------------------------------------------------------
# Tier 1 — Deterministic checks
# ---------------------------------------------------------------------------

_LEADING_PHRASES = [
    "don't you think",
    "do not you think",
    "obviously",
    "surely",
    "of course",
    "isn't it",
    "is it not",
]


def _is_double_barreled(text: str) -> bool:
    """Heuristic: detect ' and ' or ' or ' joining two non-trivial clause fragments.

    A fragment is considered non-trivial if it contains at least 2 words.
    """
    lower = text.lower()
    for conjunction in (" and ", " or "):
        if conjunction in lower:
            idx = lower.index(conjunction)
            left = lower[:idx].strip()
            right = lower[idx + len(conjunction) :].strip()
            # Both sides must have at least 2 words to be a clause
            if len(left.split()) >= 2 and len(right.split()) >= 2:
                return True
    return False


def _check_question_tier1(question: Question) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    qid = question.id
    text_lower = question.text.lower()

    # Double-barreled
    if _is_double_barreled(question.text):
        issues.append(
            ValidationIssue(
                question_id=qid,
                severity="warning",
                code="double_barreled",
                message="Question may be double-barreled: it appears to ask about two things at once.",
            )
        )

    # Scale length (single_choice and multiple_choice)
    if question.type in (QuestionType.SINGLE_CHOICE, QuestionType.MULTIPLE_CHOICE):
        n_opts = len(question.answer_options)
        if n_opts < 4:
            issues.append(
                ValidationIssue(
                    question_id=qid,
                    severity="warning",
                    code="scale_too_short",
                    message=f"Only {n_opts} option(s) provided; consider at least 4 for a meaningful scale.",
                )
            )
        elif n_opts > 7:
            issues.append(
                ValidationIssue(
                    question_id=qid,
                    severity="warning",
                    code="scale_too_long",
                    message=f"{n_opts} options may overwhelm respondents; consider 7 or fewer.",
                )
            )

    # Slider — no labels
    if question.type == QuestionType.SLIDER:
        labels = question.metadata.get("labels") or question.metadata.get("label")
        if not labels:
            issues.append(
                ValidationIssue(
                    question_id=qid,
                    severity="info",
                    code="slider_no_labels",
                    message="Slider has no label metadata; consider adding min/max labels for clarity.",
                )
            )

    # Leading language
    for phrase in _LEADING_PHRASES:
        if phrase in text_lower:
            issues.append(
                ValidationIssue(
                    question_id=qid,
                    severity="warning",
                    code="leading_language",
                    message=f"Question contains leading language: '{phrase}'.",
                )
            )
            break

    # Likert unlabelled (single_choice, 4–7 options, any option text is empty)
    if question.type == QuestionType.SINGLE_CHOICE:
        n_opts = len(question.answer_options)
        if 4 <= n_opts <= 7:
            if any(not (opt.text or "").strip() for opt in question.answer_options):
                issues.append(
                    ValidationIssue(
                        question_id=qid,
                        severity="warning",
                        code="likert_unlabelled",
                        message="One or more Likert scale options have empty text labels.",
                    )
                )

    return issues


# ---------------------------------------------------------------------------
# Tier 2 — LLM-assisted checks
# ---------------------------------------------------------------------------


def _parse_llm_issues(raw: str, question_id: str) -> list[ValidationIssue]:
    """Parse LLM JSON array of issues, with fallback to empty list on failure."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[1:end]).strip()

    try:
        data = json.loads(text)
        if not isinstance(data, list):
            return []
        issues = []
        for item in data:
            if not isinstance(item, dict):
                continue
            code = item.get("code") or "llm_issue"
            severity = item.get("severity") or "warning"
            message = item.get("message") or ""
            if severity not in ("error", "warning", "info"):
                severity = "warning"
            issues.append(
                ValidationIssue(
                    question_id=question_id,
                    severity=severity,  # type: ignore[arg-type]
                    code=code,
                    message=message,
                )
            )
        return issues
    except (json.JSONDecodeError, ValueError):
        logging.warning(
            "LLM validation response was not valid JSON; ignoring LLM tier for question %s",
            question_id,
        )
        return []


def _llm_validate_question(
    question: Question,
    llm_client: LLMClient,
    style_profile: dict | None,
) -> list[ValidationIssue]:
    from m_chat.style import build_style_context

    style_ctx = build_style_context(style_profile or {})
    prompt = (
        f"{style_ctx}\n\n"
        f"Validate the following survey question for clarity, ambiguity, and potential bias.\n"
        f"Question text: {question.text}\n"
        f"Question type: {question.type.value}\n"
        "Return a JSON array of issues: "
        '[{"code": "...", "severity": "error|warning|info", "message": "..."}]. '
        "Return an empty array [] if no issues found."
    )
    raw = llm_client.create_completion(messages=[{"role": "user", "content": prompt}])
    return _parse_llm_issues(raw, question.id)


def _llm_validate_survey_batch(
    survey: Survey,
    llm_client: LLMClient,
    style_profile: dict | None,
) -> list[ValidationIssue]:
    from m_chat.style import build_style_context

    style_ctx = build_style_context(style_profile or {})

    questions_text = "\n".join(f"  [{q.id}] {q.text}" for s in survey.sections for q in s.questions)

    prompt = (
        f"{style_ctx}\n\n"
        "Check the following survey questions for cross-question consistency, "
        "tone, and potential bias across the whole survey.\n"
        f"Questions:\n{questions_text}\n\n"
        "Return a JSON array of issues per question: "
        '[{"code": "...", "severity": "error|warning|info", "message": "...", "question_id": "..."}]. '
        "Return an empty array [] if no issues found."
    )
    raw = llm_client.create_completion(messages=[{"role": "user", "content": prompt}])

    # Parse — note items may include question_id field
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[1:end]).strip()

    try:
        data = json.loads(text)
        if not isinstance(data, list):
            return []
        issues = []
        for item in data:
            if not isinstance(item, dict):
                continue
            code = item.get("code") or "llm_issue"
            severity = item.get("severity") or "warning"
            message = item.get("message") or ""
            question_id = item.get("question_id") or "unknown"
            if severity not in ("error", "warning", "info"):
                severity = "warning"
            issues.append(
                ValidationIssue(
                    question_id=question_id,
                    severity=severity,  # type: ignore[arg-type]
                    code=code,
                    message=message,
                )
            )
        return issues
    except (json.JSONDecodeError, ValueError):
        logging.warning("LLM batch validation response was not valid JSON; ignoring LLM tier")
        return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_question(
    question: Question,
    llm_client: LLMClient | None = None,
    survey: Survey | None = None,
    style_profile: dict | None = None,
) -> list[ValidationIssue]:
    """Validate a single question.

    Tier 1 (deterministic) always runs. Tier 2 (LLM) runs only when llm_client
    is provided.

    Args:
        question: Question to validate
        llm_client: Optional LLM client for tier-2 checks
        survey: Unused at question level; reserved for future cross-question checks
        style_profile: Optional style profile for LLM context

    Returns:
        List of ValidationIssue objects
    """
    issues = _check_question_tier1(question)
    if llm_client is not None:
        issues.extend(_llm_validate_question(question, llm_client, style_profile))
    return issues


def validate_survey(
    survey: Survey,
    llm_client: LLMClient | None = None,
    style_profile: dict | None = None,
) -> list[ValidationIssue]:
    """Validate all questions in a survey.

    Runs tier-1 checks on every question. If llm_client is provided, also runs
    a single batched LLM call for cross-question consistency.

    Args:
        survey: Survey to validate
        llm_client: Optional LLM client for tier-2 checks
        style_profile: Optional style profile for LLM context

    Returns:
        List of ValidationIssue objects across all questions
    """
    issues: list[ValidationIssue] = []

    for section in survey.sections:
        for question in section.questions:
            issues.extend(_check_question_tier1(question))

    if llm_client is not None:
        issues.extend(_llm_validate_survey_batch(survey, llm_client, style_profile))

    return issues
