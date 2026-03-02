"""SurveyMonkey platform adapter (import/export only).

Handles import and export of SurveyMonkey survey JSON (the format returned
by / accepted by the SurveyMonkey REST API v3 survey detail endpoint).

Response submission requires a Team Advantage plan or higher and is out of
scope for the current MVP. capabilities() returns {"import", "export"} only.

SurveyMonkey JSON structure:
    {
      "id": "…",
      "title": "…",
      "description": "…",
      "pages": [
        {
          "id": "…",
          "title": "…",
          "description": "…",
          "position": 1,
          "questions": [
            {
              "id": "…",
              "heading": "…",     ← question text (plain-text display)
              "family": "…",      ← question type family
              "subtype": "…",     ← further refinement
              "position": 1,
              "required": false,
              "answers": {
                "choices": [{"id": "…", "text": "…", "position": 1}],
                "rows":    [{"id": "…", "text": "…"}],
                "other":   {"id": "…", "text": "Other"}
              }
            }
          ]
        }
      ]
    }

SurveyMonkey question family/subtype → internal QuestionType:
    single_choice  (any subtype)  → single_choice
    multiple_choice (any subtype) → multiple_choice
    open_ended     (any subtype)  → open_ended
    demographic    (any subtype)  → open_ended   (best-effort)
    rating         (any subtype)  → single_choice (star/number scales)
    matrix         rows+choices   → single_choice (best-effort; rows become questions)
    ranking        (any subtype)  → ranking
    slider         (any subtype)  → slider
"""

import json
import logging
import uuid
from typing import Any

from m_shared.adapters.base import SurveyAdapter
from m_shared.models.answer_option import AnswerOption
from m_shared.models.question import Question, QuestionType
from m_shared.models.section import Section
from m_shared.models.survey import Survey

logger = logging.getLogger(__name__)

_FAMILY_MAP: dict[str, QuestionType | None] = {
    "single_choice": QuestionType.SINGLE_CHOICE,
    "multiple_choice": QuestionType.MULTIPLE_CHOICE,
    "open_ended": QuestionType.OPEN_ENDED,
    "demographic": QuestionType.OPEN_ENDED,
    "rating": QuestionType.SINGLE_CHOICE,
    "matrix": QuestionType.SINGLE_CHOICE,
    "ranking": QuestionType.RANKING,
    "slider": QuestionType.SLIDER,
    "presentation": None,  # display-only elements, skip
}

# Internal QuestionType → SM family for export
_TYPE_TO_FAMILY: dict[QuestionType, str] = {
    QuestionType.SINGLE_CHOICE: "single_choice",
    QuestionType.MULTIPLE_CHOICE: "multiple_choice",
    QuestionType.OPEN_ENDED: "open_ended",
    QuestionType.RANKING: "ranking",
    QuestionType.SLIDER: "slider",
}


class SurveyMonkeyAdapter(SurveyAdapter):
    """Adapter for SurveyMonkey platform (import/export only).

    Parses and serialises SurveyMonkey survey JSON (API v3 format).
    Response submission is not supported at this plan tier.
    """

    def capabilities(self) -> set[str]:
        return {"import", "export"}

    # ------------------------------------------------------------------
    # Import
    # ------------------------------------------------------------------

    def import_survey(self, raw: str) -> Survey:
        """Parse a SurveyMonkey survey JSON string into an internal Survey.

        Args:
            raw: SurveyMonkey survey JSON as a string.

        Returns:
            Survey: The parsed survey.

        Raises:
            ValueError: If the JSON is malformed or missing required fields.
        """
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid SurveyMonkey JSON: {exc}") from exc

        survey_id = data.get("id") or str(uuid.uuid4())
        title = data.get("title") or "Untitled Survey"
        description = data.get("description") or ""

        pages: list[dict[str, Any]] = sorted(
            data.get("pages", []), key=lambda p: p.get("position", 0)
        )

        sections: list[Section] = []
        for order, page in enumerate(pages):
            section = _parse_page(page, order)
            sections.append(section)

        extra = {k: v for k, v in data.items() if k not in ("id", "title", "description", "pages")}

        return Survey(
            id=survey_id,
            title=title,
            description=description,
            sections=sections,
            metadata={"platform": "surveymonkey", "sm_id": survey_id, **extra},
        )

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_survey(self, survey: Survey) -> str:
        """Serialise an internal Survey to SurveyMonkey API v3 JSON format.

        Args:
            survey: The survey to export.

        Returns:
            str: SurveyMonkey-format JSON string.
        """
        pages: list[dict[str, Any]] = []
        for section in survey.sections:
            page_id = section.metadata.get("sm_page_id", section.id)
            questions: list[dict[str, Any]] = []

            for i, question in enumerate(section.questions, start=1):
                questions.append(_build_question_dict(question, i))

            pages.append(
                {
                    "id": str(page_id),
                    "title": section.title,
                    "description": section.description,
                    "position": section.order + 1,
                    "questions": questions,
                }
            )

        sm_id = survey.metadata.get("sm_id", survey.id)
        result: dict[str, Any] = {
            "id": str(sm_id),
            "title": survey.title,
            "description": survey.description,
            "pages": pages,
        }
        # Restore any extra metadata fields from original survey
        for k, v in survey.metadata.items():
            if k not in ("platform", "sm_id"):
                result.setdefault(k, v)

        return json.dumps(result, ensure_ascii=False, indent=2)


# ------------------------------------------------------------------
# Import helpers
# ------------------------------------------------------------------


def _parse_page(page: dict[str, Any], order: int) -> Section:
    """Convert a SurveyMonkey page dict into a Section."""
    page_id = page.get("id", str(uuid.uuid4()))
    title = page.get("title") or f"Page {order + 1}"
    description = page.get("description") or ""

    raw_questions: list[dict[str, Any]] = sorted(
        page.get("questions", []), key=lambda q: q.get("position", 0)
    )

    questions: list[Question] = []
    for q_data in raw_questions:
        position = max(0, q_data.get("position", 1) - 1)  # SM is 1-based; store 0-based
        parsed = _parse_question(q_data, position)
        if parsed is not None:
            if isinstance(parsed, list):
                questions.extend(parsed)
            else:
                questions.append(parsed)

    return Section(
        id=f"page_{page_id}",
        title=title,
        description=description,
        questions=questions,
        order=order,
        metadata={"sm_page_id": page_id},
    )


def _parse_question(q: dict[str, Any], position: int = 0) -> Question | list[Question] | None:
    """Convert a SurveyMonkey question dict into one or more internal Questions.

    Matrix questions are expanded: each row becomes a separate Question so the
    internal model (which has no matrix concept) can represent them.
    """
    family = q.get("family", "")
    subtype = q.get("subtype", "")
    q_type = _FAMILY_MAP.get(family)

    if q_type is None:
        if family:
            logger.warning(
                "Unsupported SurveyMonkey question family '%s' (id=%s) — skipping",
                family,
                q.get("id"),
            )
        return None

    qid = q.get("id", str(uuid.uuid4()))
    heading = _get_heading(q)
    required = q.get("required", False)
    answers: dict[str, Any] = q.get("answers", {})

    # Matrix: each row is a sub-question with the column choices as options
    if family == "matrix":
        return _expand_matrix(q, qid, answers, required, position)

    # Slider: extract bounds from answers.ranges or question-level attributes
    min_val = max_val = step = None
    if q_type == QuestionType.SLIDER:
        ranges = answers.get("ranges", [{}])
        first_range = ranges[0] if ranges else {}
        min_val = float(first_range.get("min", q.get("min_value", 0) or 0))
        max_val = float(first_range.get("max", q.get("max_value", 100) or 100))
        step = float(q.get("step", 1) or 1)

    answer_options = _parse_choices(answers, q_type)

    return Question(
        id=f"q_{qid}",
        text=heading,
        type=q_type,
        order=position,
        answer_options=answer_options,
        required=required,
        min_value=min_val,
        max_value=max_val,
        step=step,
        metadata={
            "platform": "surveymonkey",
            "sm_qid": qid,
            "sm_family": family,
            "sm_subtype": subtype,
        },
    )


def _get_heading(q: dict[str, Any]) -> str:
    """Extract display text from a question dict.

    SurveyMonkey stores question text in either 'heading', a 'headings' list,
    or falls back to the question id.
    """
    if "heading" in q:
        return q["heading"]
    headings = q.get("headings", [])
    if headings:
        return headings[0].get("heading", "") or headings[0].get("text", "")
    return f"Question {q.get('id', '?')}"


def _parse_choices(answers: dict[str, Any], q_type: QuestionType) -> list[AnswerOption]:
    """Extract answer options from the answers dict."""
    # Rating questions use 'choices' with numeric labels
    choices: list[dict[str, Any]] = sorted(
        answers.get("choices", []), key=lambda c: c.get("position", 0)
    )
    options: list[AnswerOption] = []
    for choice in choices:
        cid = choice.get("id", str(uuid.uuid4()))
        text = choice.get("text", str(cid))
        options.append(
            AnswerOption(
                id=f"opt_{cid}",
                text=text,
                value=cid,
                metadata={"sm_choice_id": cid},
            )
        )
    return options


def _expand_matrix(
    q: dict[str, Any],
    qid: str,
    answers: dict[str, Any],
    required: bool,
    position: int = 0,
) -> list[Question]:
    """Expand a matrix question into one Question per row."""
    rows: list[dict[str, Any]] = sorted(answers.get("rows", []), key=lambda r: r.get("position", 0))
    cols: list[dict[str, Any]] = sorted(
        answers.get("choices", []), key=lambda c: c.get("position", 0)
    )
    col_options = [
        AnswerOption(
            id=f"opt_{c.get('id', i)}",
            text=c.get("text", str(i)),
            value=c.get("id", str(i)),
            metadata={"sm_choice_id": c.get("id")},
        )
        for i, c in enumerate(cols)
    ]
    questions: list[Question] = []
    for row in rows:
        rid = row.get("id", str(uuid.uuid4()))
        row_text = row.get("text", f"Row {rid}")
        questions.append(
            Question(
                id=f"q_{qid}_row_{rid}",
                text=row_text,
                type=QuestionType.SINGLE_CHOICE,
                order=position,
                answer_options=col_options,
                required=required,
                min_value=None,
                max_value=None,
                step=None,
                metadata={
                    "platform": "surveymonkey",
                    "sm_qid": qid,
                    "sm_row_id": rid,
                    "sm_family": "matrix",
                },
            )
        )
    return questions


# ------------------------------------------------------------------
# Export helpers
# ------------------------------------------------------------------


def _build_question_dict(question: Question, position: int = 1) -> dict[str, Any]:
    """Build a SurveyMonkey question dict from an internal Question."""
    qid = question.metadata.get("sm_qid", question.id)
    family = question.metadata.get("sm_family") or _TYPE_TO_FAMILY.get(question.type, "open_ended")
    subtype = question.metadata.get("sm_subtype", "vertical")

    q_dict: dict[str, Any] = {
        "id": str(qid),
        "heading": question.text,
        "family": family,
        "subtype": subtype,
        "position": position,
        "required": question.required,
        "answers": {},
    }

    if question.answer_options:
        q_dict["answers"]["choices"] = [
            {
                "id": str(opt.metadata.get("sm_choice_id", opt.value or opt.id)),
                "text": opt.text,
                "position": i + 1,
            }
            for i, opt in enumerate(question.answer_options)
        ]

    if question.type == QuestionType.SLIDER:
        q_dict["answers"]["ranges"] = [
            {"min": question.min_value or 0, "max": question.max_value or 100}
        ]

    return q_dict
