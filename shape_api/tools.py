"""LLM tools available during the Shape chat turn.

Exposes a read tool (`get_full_survey`) plus nine mutation tools that apply
granular changes to the session's draft survey:

- ``init_survey``     — replace the whole draft (cold-start / wholesale restructure)
- ``add_section``     — insert a new section
- ``update_section``  — patch a section's title/description/metadata
- ``delete_section``  — remove a section and its questions
- ``move_section``    — change a section's position in the survey
- ``add_question``    — insert a new question into a section
- ``update_question`` — patch any field of a question
- ``delete_question`` — remove a question
- ``move_question``   — change a question's position, optionally across sections

Every mutation tool returns a JSON envelope: ``{"status": "ok",
"validation_issues": [...]}`` on success, or ``{"status": "error", "code": ...,
"message": ...}`` on a precondition failure. The dispatcher never raises for a
documented mutation error; it raises ``ValueError`` only for an unknown tool
name.
"""

import json
import logging

from pydantic import ValidationError

from m_shared.models.question import Question
from m_shared.models.section import Section
from m_shared.models.survey import Survey
from shape_api.models import QuestionPatch, SectionPatch
from shape_api.mutations import (
    ERROR_CODES,
    MutationError,
    apply_add_question,
    apply_add_section,
    apply_delete_question,
    apply_delete_section,
    apply_init_survey,
    apply_move_question,
    apply_move_section,
    apply_update_question,
    apply_update_section,
)
from shape_api.session import load_draft_survey, save_draft_survey
from shape_api.validation_engine import validate_survey

_LOGGER = logging.getLogger(__name__)


def _tool(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required},
        },
    }


_STR = {"type": "string"}
_SURVEY_PARAM = {
    "type": "object",
    "description": "A complete survey: {id, title, description, sections:[...], metadata}. "
    "Match the shape returned by get_full_survey.",
}
_SECTION_PARAM = {
    "type": "object",
    "description": "A section: {id, title, description, questions:[...], metadata}. "
    "Order is the section's position in the list, not a field — use move_section to reorder.",
}
_QUESTION_PARAM = {
    "type": "object",
    "description": "A question: {id, text, type, answer_options, min_value, max_value, step, "
    "required, metadata}. type is one of open_ended, single_choice, multiple_choice, "
    "ranking, slider, descriptive. Order is the question's position in the list, not a field — "
    "use move_question to reorder.",
}
_SECTION_PATCH_PARAM = {
    "type": "object",
    "description": "Only the section fields to change: any of {title, description, metadata}.",
}
_QUESTION_PATCH_PARAM = {
    "type": "object",
    "description": "Only the question fields to change: any of {text, type, answer_options, "
    "min_value, max_value, step, required, metadata}.",
}


GET_FULL_SURVEY_TOOL = _tool(
    "get_full_survey",
    "Return the full JSON of the current draft survey for this session. Call this before "
    "editing so you work from authoritative state: the compact summary in the system prompt "
    "omits answer options, types, required flags, numeric ranges, and metadata.",
    {},
    [],
)

INIT_SURVEY_TOOL = _tool(
    "init_survey",
    "Replace the entire draft survey. Use ONLY to create a survey from scratch or when the user "
    "explicitly asks to start over or restructure wholesale. For incremental edits use the "
    "add/update/delete tools instead.",
    {"survey": _SURVEY_PARAM},
    ["survey"],
)

ADD_SECTION_TOOL = _tool(
    "add_section",
    "Insert a new section. Optionally place it after an existing section via after_id; omit "
    "after_id to append at the end.",
    {
        "section": _SECTION_PARAM,
        "after_id": {**_STR, "description": "Insert after this section id."},
    },
    ["section"],
)

UPDATE_SECTION_TOOL = _tool(
    "update_section",
    "Patch a section's title, description, or metadata. Does NOT change its questions or "
    "position — use the question tools or move_section for those. If the section id is unknown, "
    "call get_full_survey.",
    {"section_id": _STR, "patch": _SECTION_PATCH_PARAM},
    ["section_id", "patch"],
)

MOVE_SECTION_TOOL = _tool(
    "move_section",
    "Change a section's position in the survey. Place it after an existing section via after_id; "
    "omit after_id to move it to the front. If the section id is unknown, call get_full_survey.",
    {
        "section_id": _STR,
        "after_id": {**_STR, "description": "Place after this section id; omit to move to front."},
    },
    ["section_id"],
)

DELETE_SECTION_TOOL = _tool(
    "delete_section",
    "Remove a section and all of its questions.",
    {"section_id": _STR},
    ["section_id"],
)

ADD_QUESTION_TOOL = _tool(
    "add_question",
    "Insert a new question into a section. Optionally place it after an existing question via "
    "after_id; omit to append. To reposition an existing question (within or across sections) "
    "use move_question — do not delete and re-add it.",
    {
        "section_id": _STR,
        "question": _QUESTION_PARAM,
        "after_id": {**_STR, "description": "Insert after this question id."},
    },
    ["section_id", "question"],
)

UPDATE_QUESTION_TOOL = _tool(
    "update_question",
    "Patch any fields of a question (text, type, answer_options, etc). If the question id is "
    "unknown, call get_full_survey.",
    {"question_id": _STR, "patch": _QUESTION_PATCH_PARAM},
    ["question_id", "patch"],
)

DELETE_QUESTION_TOOL = _tool(
    "delete_question",
    "Remove a question from wherever it currently lives.",
    {"question_id": _STR},
    ["question_id"],
)

MOVE_QUESTION_TOOL = _tool(
    "move_question",
    "Change a question's position. Place it after an existing question via after_id; omit "
    "after_id to move it to the front of the target section. Pass section_id to move it into a "
    "different section (its id and all other fields are preserved). If the question id is "
    "unknown, call get_full_survey.",
    {
        "question_id": _STR,
        "after_id": {**_STR, "description": "Place after this question id; omit to move to front."},
        "section_id": {
            **_STR,
            "description": "Target section id; omit to stay in the current one.",
        },
    },
    ["question_id"],
)

ALL_TOOLS: list[dict] = [
    GET_FULL_SURVEY_TOOL,
    INIT_SURVEY_TOOL,
    ADD_SECTION_TOOL,
    UPDATE_SECTION_TOOL,
    DELETE_SECTION_TOOL,
    MOVE_SECTION_TOOL,
    ADD_QUESTION_TOOL,
    UPDATE_QUESTION_TOOL,
    DELETE_QUESTION_TOOL,
    MOVE_QUESTION_TOOL,
]

NO_DRAFT_SENTINEL = '{"survey": null}'


def _apply_mutation(name: str, arguments: dict, survey: Survey | None) -> Survey:
    """Construct typed inputs from `arguments` and apply the named mutation.

    Raises a MutationError subclass on precondition failure, pydantic
    ValidationError on a malformed payload, or ValueError for an unknown name.
    """
    # Coerce id arguments to str: a missing id becomes "" so the mutation layer
    # raises a clean not-found error rather than the dispatcher crashing.
    section_id = str(arguments.get("section_id") or "")
    question_id = str(arguments.get("question_id") or "")

    if name == "init_survey":
        return apply_init_survey(Survey.model_validate(arguments.get("survey")))
    if name == "add_section":
        return apply_add_section(
            survey, Section.model_validate(arguments.get("section")), arguments.get("after_id")
        )
    if name == "update_section":
        return apply_update_section(
            survey, section_id, SectionPatch.model_validate(arguments.get("patch", {}))
        )
    if name == "delete_section":
        return apply_delete_section(survey, section_id)
    if name == "move_section":
        return apply_move_section(survey, section_id, arguments.get("after_id"))
    if name == "add_question":
        return apply_add_question(
            survey,
            section_id,
            Question.model_validate(arguments.get("question")),
            arguments.get("after_id"),
        )
    if name == "update_question":
        return apply_update_question(
            survey, question_id, QuestionPatch.model_validate(arguments.get("patch", {}))
        )
    if name == "delete_question":
        return apply_delete_question(survey, question_id)
    if name == "move_question":
        return apply_move_question(
            survey, question_id, arguments.get("after_id"), arguments.get("section_id")
        )
    raise ValueError(f"Unknown tool: {name}")


def dispatch_tool_call(name: str, arguments: dict, base_path: str, session_id: str) -> str:
    """Run a chat-turn tool call and return a JSON string result.

    Raises:
        ValueError: if `name` is not a registered tool.
    """
    if name == "get_full_survey":
        survey = load_draft_survey(base_path, session_id)
        _LOGGER.info("tool_call session_id=%s name=%s status=ok", session_id, name)
        return NO_DRAFT_SENTINEL if survey is None else survey.model_dump_json()

    survey = load_draft_survey(base_path, session_id)
    try:
        new_survey = _apply_mutation(name, arguments, survey)
    except MutationError as exc:
        code = ERROR_CODES[type(exc)]
        _LOGGER.info("tool_call session_id=%s name=%s status=error code=%s", session_id, name, code)
        return json.dumps({"status": "error", "code": code, "message": str(exc)})
    except ValidationError as exc:
        _LOGGER.info(
            "tool_call session_id=%s name=%s status=error code=invalid_patch", session_id, name
        )
        return json.dumps({"status": "error", "code": "invalid_patch", "message": str(exc)})

    save_draft_survey(base_path, session_id, new_survey)
    issues = validate_survey(new_survey)
    _LOGGER.info(
        "tool_call session_id=%s name=%s status=ok issues=%d", session_id, name, len(issues)
    )
    return json.dumps({"status": "ok", "validation_issues": [i.model_dump() for i in issues]})
