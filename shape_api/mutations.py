"""Pure survey mutation functions shared by the LLM tools and HTTP endpoints.

Each function takes the current draft `Survey` (or `None`) and returns a new
`Survey`, raising a `MutationError` subclass on any precondition failure. There
is no I/O here: callers are responsible for loading, persisting, and validating
the result.
"""

from __future__ import annotations

from pydantic import ValidationError

from m_shared.models.question import Question
from m_shared.models.section import Section
from m_shared.models.survey import Survey
from shape_api.models import QuestionPatch, SectionPatch


class MutationError(Exception):
    """Base class for survey mutation precondition failures."""


class NoSurveyDraft(MutationError):
    """A mutation other than init was attempted with no draft present."""


class SectionNotFound(MutationError):
    """The referenced section id does not exist in the draft."""


class QuestionNotFound(MutationError):
    """The referenced question id does not exist in the draft."""


class DuplicateId(MutationError):
    """An add was attempted with an id that already exists."""


class InvalidPatch(MutationError):
    """A patch failed validation against the target model."""


# Maps each error class to the stable code surfaced to LLM tools and clients.
ERROR_CODES: dict[type[MutationError], str] = {
    NoSurveyDraft: "no_survey_draft",
    SectionNotFound: "section_not_found",
    QuestionNotFound: "question_not_found",
    DuplicateId: "duplicate_id",
    InvalidPatch: "invalid_patch",
}


def _require_survey(survey: Survey | None) -> Survey:
    if survey is None:
        raise NoSurveyDraft("No survey draft exists. Call init_survey first.")
    return survey.model_copy(deep=True)


def _find_section(survey: Survey, section_id: str) -> Section:
    for section in survey.sections:
        if section.id == section_id:
            return section
    raise SectionNotFound(
        f"Section {section_id!r} not found. Call get_full_survey to list current section ids."
    )


def _insert_after(items: list, item, after_id: str | None) -> None:
    """Insert `item` after the element whose id == after_id, else append."""
    if after_id is not None:
        for i, existing in enumerate(items):
            if existing.id == after_id:
                items.insert(i + 1, item)
                return
    items.append(item)


def apply_init_survey(survey: Survey) -> Survey:
    """Set the draft to a complete survey (cold-start or wholesale replace)."""
    return survey


def apply_add_section(
    survey: Survey | None, section: Section, after_id: str | None = None
) -> Survey:
    new = _require_survey(survey)
    if any(s.id == section.id for s in new.sections):
        raise DuplicateId(f"Section id {section.id!r} already exists; ids must be unique.")
    _insert_after(new.sections, section, after_id)
    return new


def apply_update_section(survey: Survey | None, section_id: str, patch: SectionPatch) -> Survey:
    new = _require_survey(survey)
    section = _find_section(new, section_id)
    merged = {**section.model_dump(), **patch.model_dump(exclude_unset=True)}
    try:
        updated = Section.model_validate(merged)
    except ValidationError as exc:
        raise InvalidPatch(str(exc)) from exc
    new.sections[new.sections.index(section)] = updated
    return new


def apply_delete_section(survey: Survey | None, section_id: str) -> Survey:
    new = _require_survey(survey)
    section = _find_section(new, section_id)
    new.sections.remove(section)
    return new


def apply_add_question(
    survey: Survey | None, section_id: str, question: Question, after_id: str | None = None
) -> Survey:
    new = _require_survey(survey)
    section = _find_section(new, section_id)
    existing_ids = {q.id for s in new.sections for q in s.questions}
    if question.id in existing_ids:
        raise DuplicateId(f"Question id {question.id!r} already exists; ids must be unique.")
    _insert_after(section.questions, question, after_id)
    return new


def apply_update_question(survey: Survey | None, question_id: str, patch: QuestionPatch) -> Survey:
    new = _require_survey(survey)
    for section in new.sections:
        for i, question in enumerate(section.questions):
            if question.id == question_id:
                merged = {**question.model_dump(), **patch.model_dump(exclude_unset=True)}
                try:
                    section.questions[i] = Question.model_validate(merged)
                except ValidationError as exc:
                    raise InvalidPatch(str(exc)) from exc
                return new
    raise QuestionNotFound(
        f"Question {question_id!r} not found. Call get_full_survey to list current question ids."
    )


def apply_delete_question(survey: Survey | None, question_id: str) -> Survey:
    new = _require_survey(survey)
    for section in new.sections:
        for question in section.questions:
            if question.id == question_id:
                section.questions.remove(question)
                return new
    raise QuestionNotFound(
        f"Question {question_id!r} not found. Call get_full_survey to list current question ids."
    )
