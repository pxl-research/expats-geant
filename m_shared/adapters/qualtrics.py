"""Qualtrics platform adapter.

Handles import/export of Qualtrics Survey Format (QSF) JSON files and response
submission via the Qualtrics Response Import API v3.

QSF format overview:
    - "SurveyEntry": survey-level metadata (SurveyID, SurveyName, SurveyDescription)
    - "SurveyElements": list of typed elements
        - Element "BL": block definitions (→ Sections); Payload is a list of block dicts,
          each with "ID", "Description", "BlockElements" (ordered question refs)
        - Element "FL": survey flow (block ordering); Payload.Flow is a list of
          {Type, ID} dicts — used to determine section order
        - Element "SQ": a single question; Payload contains full question data

QSF question type / selector → internal QuestionType:
    MC + SAVR | SACOL | SAHR | DL | SB  → single_choice
    MC + MAVR | MACOL | MAHR            → multiple_choice
    TE (any selector)                   → open_ended
    Slider                              → slider
    RO                                  → ranking
    Matrix                              → single_choice (best-effort; subquestions skipped)

Qualtrics Response Import API:
    POST https://{datacenter}.qualtrics.com/API/v3/surveys/{surveyId}/responses
    Header: X-API-TOKEN: <token>
    Body:   {"values": {"QID1": "1", "QID2": ["1", "3"]}}
"""

import json
import logging
import uuid
from typing import Any

import requests

from m_shared.adapters.base import SurveyAdapter
from m_shared.models.answer_option import AnswerOption
from m_shared.models.question import Question, QuestionType
from m_shared.models.response import Response
from m_shared.models.section import Section
from m_shared.models.survey import Survey

logger = logging.getLogger(__name__)

# (QuestionType, Selector) → single/multi choice
_MC_SINGLE_SELECTORS = {"SAVR", "SACOL", "SAHR", "DL", "SB"}
_MC_MULTI_SELECTORS = {"MAVR", "MACOL", "MAHR"}

# Internal QuestionType → QSF export defaults
_EXPORT_TYPE: dict[QuestionType, tuple[str, str]] = {
    QuestionType.SINGLE_CHOICE: ("MC", "SAVR"),
    QuestionType.MULTIPLE_CHOICE: ("MC", "MAVR"),
    QuestionType.OPEN_ENDED: ("TE", "ML"),
    QuestionType.RANKING: ("RO", "Rank"),
    QuestionType.SLIDER: ("Slider", "HSLIDER"),
}

_API_BASE = "https://{datacenter}.qualtrics.com/API/v3"


class QualtricsAdapter(SurveyAdapter):
    """Adapter for the Qualtrics survey platform.

    Supports import/export of QSF (Qualtrics Survey Format) JSON files and
    response submission via the Qualtrics Response Import API v3.

    Args:
        api_token: Qualtrics API token. Required only for submit_responses().
        datacenter_id: Qualtrics datacenter ID (e.g. "iad1", "ca1").
                       Required only for submit_responses().
    """

    def __init__(
        self,
        api_token: str | None = None,
        datacenter_id: str | None = None,
    ) -> None:
        self._api_token = api_token
        self._datacenter_id = datacenter_id

    def capabilities(self) -> set[str]:
        return {"import", "export", "submit"}

    # ------------------------------------------------------------------
    # Import
    # ------------------------------------------------------------------

    def import_survey(self, raw: str) -> Survey:
        """Parse a QSF JSON string into an internal Survey.

        Args:
            raw: QSF JSON content as a string.

        Returns:
            Survey: The parsed survey.

        Raises:
            ValueError: If the JSON is malformed or missing required fields.
        """
        try:
            qsf = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid QSF JSON: {exc}") from exc

        entry = qsf.get("SurveyEntry", {})
        elements = qsf.get("SurveyElements", [])

        survey_id = entry.get("SurveyID") or str(uuid.uuid4())
        title = entry.get("SurveyName") or "Untitled Survey"
        description = entry.get("SurveyDescription") or ""

        # Index questions by QID
        questions_by_qid: dict[str, dict[str, Any]] = {}
        for el in elements:
            if el.get("Element") == "SQ":
                payload = el.get("Payload", {})
                qid = payload.get("QuestionID")
                if qid:
                    questions_by_qid[qid] = payload

        # Determine block order from the flow element (FL), fallback to BL order
        block_order = _extract_block_order(elements)

        # Index blocks by ID
        blocks_by_id: dict[str, dict[str, Any]] = {}
        for el in elements:
            if el.get("Element") == "BL":
                for block in _normalise_bl_payload(el.get("Payload", [])):
                    bid = block.get("ID")
                    if bid and block.get("Type") != "Trash":
                        blocks_by_id[bid] = block

        # Build sections in flow order
        if block_order:
            ordered_blocks = [blocks_by_id[bid] for bid in block_order if bid in blocks_by_id]
        else:
            ordered_blocks = list(blocks_by_id.values())

        sections: list[Section] = []
        for order, block in enumerate(ordered_blocks):
            bid = block.get("ID", f"blk_{order}")
            block_name = block.get("Description") or f"Section {order + 1}"
            qids_in_block = [
                el["QuestionID"]
                for el in block.get("BlockElements", [])
                if el.get("Type") == "Question" and el.get("QuestionID")
            ]

            questions: list[Question] = []
            for q_order, qid in enumerate(qids_in_block):
                payload = questions_by_qid.get(qid)
                if payload is None:
                    logger.warning("Block references unknown QID '%s' — skipping", qid)
                    continue
                question = _build_question(payload, q_order)
                if question is not None:
                    questions.append(question)

            sections.append(
                Section(
                    id=f"blk_{bid}",
                    title=block_name,
                    description="",
                    questions=questions,
                    order=order,
                    metadata={"qsf_block_id": bid},
                )
            )

        extra_meta = {
            k: v
            for k, v in entry.items()
            if k not in ("SurveyID", "SurveyName", "SurveyDescription")
        }

        return Survey(
            id=survey_id,
            title=title,
            description=description,
            sections=sections,
            metadata={"platform": "qualtrics", "qsf_survey_id": survey_id, **extra_meta},
        )

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_survey(self, survey: Survey) -> str:
        """Serialize an internal Survey to QSF JSON.

        Args:
            survey: The survey to export.

        Returns:
            str: QSF JSON string suitable for import into Qualtrics.
        """
        survey_id = survey.metadata.get("qsf_survey_id", f"SV_{survey.id}")
        elements: list[dict[str, Any]] = []

        # FL (flow)
        flow_entries: list[dict[str, Any]] = []
        block_elements_by_bid: dict[str, list[dict[str, Any]]] = {}
        sq_elements: list[dict[str, Any]] = []

        for section in survey.sections:
            bid = section.metadata.get("qsf_block_id", section.id)
            flow_entries.append({"Type": "Block", "ID": str(bid), "FlowID": f"FL_{bid}"})
            block_qrefs: list[dict[str, Any]] = []

            for question in section.questions:
                qid = question.metadata.get("qsf_qid", f"QID_{question.id}")
                block_qrefs.append({"Type": "Question", "QuestionID": qid})
                sq_elements.append(_build_sq_element(survey_id, question, qid))

            block_elements_by_bid[str(bid)] = block_qrefs

        elements.append(
            {
                "SurveyID": survey_id,
                "Element": "FL",
                "Payload": {
                    "Flow": flow_entries,
                    "Properties": {"Count": len(flow_entries)},
                    "FlowID": "FL_1",
                    "Type": "Root",
                },
            }
        )

        # BL (blocks)
        bl_payload: list[dict[str, Any]] = []
        for section in survey.sections:
            bid = str(section.metadata.get("qsf_block_id", section.id))
            bl_payload.append(
                {
                    "Type": "Default",
                    "Description": section.title,
                    "ID": bid,
                    "BlockElements": block_elements_by_bid.get(bid, []),
                }
            )

        elements.append(
            {
                "SurveyID": survey_id,
                "Element": "BL",
                "Payload": bl_payload,
            }
        )

        elements.extend(sq_elements)

        qsf = {
            "SurveyEntry": {
                "SurveyID": survey_id,
                "SurveyName": survey.title,
                "SurveyDescription": survey.description,
                **{
                    k: v
                    for k, v in survey.metadata.items()
                    if k not in ("platform", "qsf_survey_id")
                },
            },
            "SurveyElements": elements,
        }

        return json.dumps(qsf, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------
    # Submit
    # ------------------------------------------------------------------

    def submit_responses(self, survey_id: str, responses: list[Response]) -> None:
        """Submit responses via the Qualtrics Response Import API v3.

        Args:
            survey_id: The Qualtrics survey ID (e.g. "SV_xxxxxxxx").
            responses: Responses to submit.

        Raises:
            ValueError: If API credentials are not configured.
            RuntimeError: If the API call fails.
        """
        if not self._api_token or not self._datacenter_id:
            raise ValueError(
                "Qualtrics api_token and datacenter_id must be set to submit responses."
            )

        url = f"{_API_BASE.format(datacenter=self._datacenter_id)}/surveys/{survey_id}/responses"
        headers = {
            "X-API-TOKEN": self._api_token,
            "Content-Type": "application/json",
        }
        values = _responses_to_qualtrics_format(responses)
        payload = {"values": values}

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(f"Qualtrics response import failed: {exc}") from exc

        try:
            body = resp.json()
        except ValueError as exc:
            raise RuntimeError(
                f"Qualtrics returned non-JSON response (HTTP {resp.status_code}): "
                f"{resp.text[:200]!r}"
            ) from exc
        if body.get("meta", {}).get("httpStatus") not in ("200 - OK", "201 - Created", None):
            raise RuntimeError(f"Qualtrics API error: {body.get('meta')}")

        logger.info("Submitted %d responses to Qualtrics survey %s", len(responses), survey_id)


# ------------------------------------------------------------------
# Import helpers
# ------------------------------------------------------------------


def _normalise_bl_payload(payload: Any) -> list[dict[str, Any]]:
    """BL Payload may be a list or a dict keyed by block ID."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        return list(payload.values())
    return []


def _extract_block_order(elements: list[dict[str, Any]]) -> list[str]:
    """Return block IDs in flow order from the FL element, or [] if absent.

    Qualtrics uses both "Block" and "Standard" as flow entry types for regular
    survey blocks. Other types (Branch, EmbeddedData, EndSurvey, etc.) are skipped.
    """
    _BLOCK_TYPES = {"Block", "Standard"}
    for el in elements:
        if el.get("Element") == "FL":
            flow = el.get("Payload", {})
            if isinstance(flow, dict):
                return [
                    entry["ID"]
                    for entry in flow.get("Flow", [])
                    if entry.get("Type") in _BLOCK_TYPES and entry.get("ID")
                ]
    return []


def _build_question(payload: dict[str, Any], order: int = 0) -> Question | None:
    """Convert a QSF SQ payload into an internal Question."""
    qid = payload.get("QuestionID", str(uuid.uuid4()))
    text = payload.get("QuestionText") or f"Question {qid}"
    # Strip basic HTML tags that Qualtrics embeds in question text
    text = _strip_html(text)

    q_type_code = payload.get("QuestionType", "")
    selector = payload.get("Selector", "")
    q_type = _map_question_type(q_type_code, selector)

    if q_type is None:
        logger.warning(
            "Unsupported QSF question type '%s'/'%s' (QID=%s) — skipping",
            q_type_code,
            selector,
            qid,
        )
        return None

    answer_options: list[AnswerOption] = []
    if q_type in (QuestionType.SINGLE_CHOICE, QuestionType.MULTIPLE_CHOICE, QuestionType.RANKING):
        # Matrix/Likert questions store scale points in "Answers"; all others use "Choices"
        q_type_code = payload.get("QuestionType", "")
        if q_type_code == "Matrix":
            raw_choices: dict[str, Any] = payload.get("Answers", {})
            choice_order: list[str] = [
                str(c) for c in payload.get("AnswerOrder", list(raw_choices.keys()))
            ]
        else:
            raw_choices = payload.get("Choices", {})
            choice_order = [str(c) for c in payload.get("ChoiceOrder", list(raw_choices.keys()))]
        for code in choice_order:
            if code not in raw_choices:
                continue
            choice_text = _strip_html(raw_choices[code].get("Display", str(code)))
            answer_options.append(
                AnswerOption(
                    id=f"opt_{code}",
                    text=choice_text,
                    value=code,
                    metadata={"qsf_code": code},
                )
            )

    min_val = max_val = step = None
    if q_type == QuestionType.SLIDER:
        cfg = payload.get("Configuration", {})
        min_val = float(cfg.get("CSSliderMin", 0))
        max_val = float(cfg.get("CSSliderMax", 100))
        grid_lines = cfg.get("GridLines")
        if grid_lines is not None:
            step = (max_val - min_val) / max(int(grid_lines), 1)
        else:
            step = 1.0

    required = payload.get("Validation", {}).get("Settings", {}).get("ForceResponse") == "ON"

    return Question(
        id=f"q_{qid}",
        text=text,
        type=q_type,
        order=order,
        answer_options=answer_options,
        required=required,
        min_value=min_val,
        max_value=max_val,
        step=step,
        metadata={
            "platform": "qualtrics",
            "qsf_qid": qid,
            "qsf_type": q_type_code,
            "qsf_selector": selector,
        },
    )


def _map_question_type(q_type_code: str, selector: str) -> QuestionType | None:
    if q_type_code == "MC":
        if selector in _MC_SINGLE_SELECTORS:
            return QuestionType.SINGLE_CHOICE
        if selector in _MC_MULTI_SELECTORS:
            return QuestionType.MULTIPLE_CHOICE
        # Default MC to single if selector is unknown
        return QuestionType.SINGLE_CHOICE
    if q_type_code == "TE":
        return QuestionType.OPEN_ENDED
    if q_type_code == "Slider":
        return QuestionType.SLIDER
    if q_type_code == "RO":
        return QuestionType.RANKING
    if q_type_code == "Matrix":
        return QuestionType.SINGLE_CHOICE  # best-effort
    return None


def _strip_html(text: str) -> str:
    """Remove simple HTML tags from Qualtrics question/choice text."""
    import re

    return re.sub(r"<[^>]+>", "", text).strip()


# ------------------------------------------------------------------
# Export helpers
# ------------------------------------------------------------------


def _build_sq_element(survey_id: str, question: Question, qid: str) -> dict[str, Any]:
    """Build a QSF SQ element dict from an internal Question."""
    q_type_code, selector = _EXPORT_TYPE.get(question.type, ("TE", "ML"))
    # Restore original QSF type/selector if stored in metadata
    q_type_code = question.metadata.get("qsf_type", q_type_code)
    selector = question.metadata.get("qsf_selector", selector)

    payload: dict[str, Any] = {
        "QuestionID": qid,
        "DataExportTag": qid,
        "QuestionText": question.text,
        "QuestionType": q_type_code,
        "Selector": selector,
        "Validation": {
            "Settings": {
                "ForceResponse": "ON" if question.required else "OFF",
                "Type": "None",
            }
        },
    }

    if question.answer_options:
        choices: dict[str, Any] = {}
        choice_order: list[str] = []
        for opt in question.answer_options:
            code = str(opt.metadata.get("qsf_code", opt.value or opt.id))
            choices[code] = {"Display": opt.text}
            choice_order.append(code)
        payload["Choices"] = choices
        payload["ChoiceOrder"] = choice_order

    if question.type == QuestionType.SLIDER:
        payload["Configuration"] = {
            "CSSliderMin": int(question.min_value or 0),
            "CSSliderMax": int(question.max_value or 100),
            "GridLines": int((question.max_value - question.min_value) / (question.step or 1))
            if question.min_value is not None and question.max_value is not None
            else 100,
            "NumDecimals": "0",
            "ShowValue": True,
        }

    return {
        "SurveyID": survey_id,
        "Element": "SQ",
        "Payload": payload,
    }


# ------------------------------------------------------------------
# Submit helpers
# ------------------------------------------------------------------


def _responses_to_qualtrics_format(responses: list[Response]) -> dict[str, Any]:
    """Convert internal Response objects to the Qualtrics response values dict.

    Qualtrics expects QIDs as keys (e.g. "QID1") and answer codes as values.
    For multiple choice / ranking: list of choice codes.
    For open-ended / slider: string value.
    """
    values: dict[str, Any] = {}
    for resp in responses:
        qid = resp.metadata.get("qsf_qid", resp.question_id)
        value = resp.answer_value
        if isinstance(value, list):
            values[qid] = value
        else:
            values[qid] = str(value) if value is not None else ""
    return values
