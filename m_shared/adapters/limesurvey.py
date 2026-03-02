"""LimeSurvey platform adapter.

Handles import/export of LimeSurvey Structure (LSS) XML files and response
submission via the LimeSurvey RemoteControl 2 JSON-RPC API.

LSS format overview:
    - Root element: <document> containing <surveys>, <groups>, <questions>, <answers>
    - surveys/rows/row: survey-level metadata (sid, surveyls_title, surveyls_description)
    - groups/rows/row: question groups (gid, group_name, description, group_order)
    - questions/rows/row: questions (qid, gid, type, question, mandatory)
    - answers/rows/row: answer options for choice questions (qid, code, answer, sortorder)

LimeSurvey question types mapped to internal QuestionType:
    L, O, !  → single_choice  (radio list, list with comment, list dropdown)
    M        → multiple_choice
    T, S, U  → open_ended     (long/short/huge text)
    R        → ranking
    N        → slider         (Numerical input — mapped to slider with no range)
"""

import json
import logging
import uuid
from typing import Any
from xml.etree import ElementTree as ET
from xml.etree.ElementTree import Element

import defusedxml.ElementTree as defused_ET
import requests

from m_shared.adapters.base import SurveyAdapter
from m_shared.models.answer_option import AnswerOption
from m_shared.models.question import Question, QuestionType
from m_shared.models.response import Response
from m_shared.models.section import Section
from m_shared.models.survey import Survey

logger = logging.getLogger(__name__)

# LimeSurvey type codes → internal QuestionType
_LS_TYPE_MAP: dict[str, QuestionType] = {
    "L": QuestionType.SINGLE_CHOICE,
    "O": QuestionType.SINGLE_CHOICE,
    "!": QuestionType.SINGLE_CHOICE,
    "1": QuestionType.SINGLE_CHOICE,  # array dual scale
    "5": QuestionType.SINGLE_CHOICE,  # 5-point choice
    "M": QuestionType.MULTIPLE_CHOICE,
    "P": QuestionType.MULTIPLE_CHOICE,  # multiple choice with comments
    "T": QuestionType.OPEN_ENDED,
    "S": QuestionType.OPEN_ENDED,
    "U": QuestionType.OPEN_ENDED,
    "R": QuestionType.RANKING,
    "N": QuestionType.SLIDER,
    "K": QuestionType.SLIDER,  # numerical multi
}

# Internal QuestionType → LimeSurvey type code (for export)
_INTERNAL_TO_LS_TYPE: dict[QuestionType, str] = {
    QuestionType.SINGLE_CHOICE: "L",
    QuestionType.MULTIPLE_CHOICE: "M",
    QuestionType.OPEN_ENDED: "T",
    QuestionType.RANKING: "R",
    QuestionType.SLIDER: "N",
}


def _text(element: Element | None) -> str:
    """Safely extract stripped text content from an XML element."""
    if element is None:
        return ""
    return (element.text or "").strip()


class LimeSurveyAdapter(SurveyAdapter):
    """Adapter for LimeSurvey platform.

    Supports import and export of LSS (LimeSurvey Structure) XML files and
    response submission via the RemoteControl 2 JSON-RPC API.

    Args:
        api_url: Base URL of the LimeSurvey RemoteControl 2 endpoint,
                 e.g. "https://survey.example.com/index.php/admin/remotecontrol".
                 Required only when calling submit_responses().
        username: LimeSurvey admin username for API authentication.
        password: LimeSurvey admin password for API authentication.
    """

    def __init__(
        self,
        api_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        self._api_url = api_url
        self._username = username
        self._password = password

    def capabilities(self) -> set[str]:
        return {"import", "export", "submit"}

    # ------------------------------------------------------------------
    # Import
    # ------------------------------------------------------------------

    def import_survey(self, raw: str) -> Survey:
        """Parse a LimeSurvey LSS XML string into an internal Survey.

        Args:
            raw: LSS XML content as a string.

        Returns:
            Survey: The parsed survey.

        Raises:
            ValueError: If the XML is malformed or missing required fields.
        """
        try:
            root = defused_ET.fromstring(raw)
        except ET.ParseError as exc:
            raise ValueError(f"Invalid LSS XML: {exc}") from exc

        survey = self._parse_survey(root)
        groups = self._parse_groups(root)
        questions_by_gid = self._parse_questions(root)
        answers_by_qid = self._parse_answers(root)

        sections: list[Section] = []
        for order, (gid, group_meta) in enumerate(groups.items()):
            raw_questions = questions_by_qid_in_group(questions_by_gid, gid)
            questions: list[Question] = []
            for q_meta in raw_questions:
                question = self._build_question(q_meta, answers_by_qid)
                if question is not None:
                    questions.append(question)

            sections.append(
                Section(
                    id=f"grp_{gid}",
                    title=group_meta["title"],
                    description=group_meta["description"],
                    questions=questions,
                    order=order,
                    metadata={"ls_gid": gid},
                )
            )

        return Survey(
            id=survey["sid"],
            title=survey["title"],
            description=survey["description"],
            sections=sections,
            metadata={"platform": "limesurvey", "ls_sid": survey["sid"], **survey["extra"]},
        )

    def _parse_survey(self, root: Element) -> dict[str, Any]:
        """Extract survey-level metadata from the LSS root element."""
        row = root.find(".//surveys/rows/row")
        if row is None:
            raise ValueError("LSS XML missing <surveys> section")

        sid = _text(row.find("sid")) or str(uuid.uuid4())
        title = (
            _text(row.find("surveyls_title"))
            or _text(row.find("surveyls_surveys/row/surveyls_title"))
            or "Untitled Survey"
        )
        description = _text(row.find("surveyls_description")) or ""

        extra: dict[str, Any] = {}
        for child in row:
            if child.tag not in ("sid", "surveyls_title", "surveyls_description"):
                extra[child.tag] = child.text

        return {"sid": sid, "title": title, "description": description, "extra": extra}

    def _parse_groups(self, root: Element) -> dict[str, dict[str, Any]]:
        """Return ordered dict of gid → group metadata."""
        groups: dict[str, dict[str, Any]] = {}
        for row in root.findall(".//groups/rows/row"):
            gid = _text(row.find("gid"))
            if not gid:
                continue
            order_el = row.find("group_order")
            groups[gid] = {
                "title": _text(row.find("group_name")) or f"Section {gid}",
                "description": _text(row.find("description")) or "",
                "order": int(order_el.text) if order_el is not None and order_el.text else 0,
            }
        # Sort by declared order
        return dict(sorted(groups.items(), key=lambda kv: kv[1]["order"]))

    def _parse_questions(self, root: Element) -> dict[str, list[dict[str, Any]]]:
        """Return dict of gid → list of question metadata dicts."""
        by_gid: dict[str, list[dict[str, Any]]] = {}
        for row in root.findall(".//questions/rows/row"):
            gid = _text(row.find("gid"))
            qid = _text(row.find("qid"))
            parent_qid = _text(row.find("parent_qid"))
            if not qid or (parent_qid and parent_qid != "0"):  # skip sub-questions
                continue
            q_meta: dict[str, Any] = {
                "qid": qid,
                "gid": gid,
                "type": _text(row.find("type")),
                "text": _text(row.find("question")) or f"Question {qid}",
                "mandatory": _text(row.find("mandatory")) in ("Y", "y", "1"),
                "order": int(_text(row.find("question_order")) or "0"),
            }
            for child in row:
                if child.tag not in (
                    "qid",
                    "gid",
                    "type",
                    "question",
                    "mandatory",
                    "question_order",
                    "parent_qid",
                ):
                    q_meta.setdefault("extra", {})[child.tag] = child.text

            by_gid.setdefault(gid, []).append(q_meta)

        for gid in by_gid:
            by_gid[gid].sort(key=lambda q: q["order"])

        return by_gid

    def _parse_answers(self, root: Element) -> dict[str, list[dict[str, Any]]]:
        """Return dict of qid → list of answer option metadata."""
        by_qid: dict[str, list[dict[str, Any]]] = {}
        for row in root.findall(".//answers/rows/row"):
            qid = _text(row.find("qid"))
            if not qid:
                continue
            by_qid.setdefault(qid, []).append(
                {
                    "code": _text(row.find("code")),
                    "text": _text(row.find("answer")) or _text(row.find("code")),
                    "order": int(_text(row.find("sortorder")) or "0"),
                }
            )

        for qid in by_qid:
            by_qid[qid].sort(key=lambda a: a["order"])

        return by_qid

    def _build_question(
        self,
        q_meta: dict[str, Any],
        answers_by_qid: dict[str, list[dict[str, Any]]],
    ) -> Question | None:
        """Convert raw question metadata into an internal Question object."""
        ls_type = q_meta["type"]
        q_type = _LS_TYPE_MAP.get(ls_type)
        if q_type is None:
            logger.warning(
                "Unsupported LimeSurvey question type '%s' (qid=%s) — skipping",
                ls_type,
                q_meta["qid"],
            )
            return None

        qid = q_meta["qid"]
        raw_options = answers_by_qid.get(qid, [])
        answer_options = [
            AnswerOption(
                id=f"opt_{opt['code']}",
                text=opt["text"],
                value=opt["code"],
                metadata={"ls_code": opt["code"]},
            )
            for opt in raw_options
        ]

        # Slider bounds: LimeSurvey stores these as question attributes (not parsed here),
        # so we default to 0–100 for slider types unless metadata overrides.
        min_val = max_val = step = None
        if q_type == QuestionType.SLIDER:
            min_val = float(q_meta.get("extra", {}).get("min_num", 0) or 0)
            max_val = float(q_meta.get("extra", {}).get("max_num", 100) or 100)
            step = float(q_meta.get("extra", {}).get("slider_accuracy", 1) or 1)

        return Question(
            id=f"q_{qid}",
            text=q_meta["text"],
            type=q_type,
            order=max(0, q_meta["order"] - 1),
            answer_options=answer_options,
            required=q_meta["mandatory"],
            min_value=min_val,
            max_value=max_val,
            step=step,
            metadata={
                "platform": "limesurvey",
                "ls_qid": qid,
                "ls_type": ls_type,
                **q_meta.get("extra", {}),
            },
        )

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_survey(self, survey: Survey) -> str:
        """Serialize an internal Survey to LimeSurvey LSS XML format.

        Args:
            survey: The survey to serialize.

        Returns:
            str: LSS XML string suitable for import into LimeSurvey.
        """
        root = ET.Element("document")

        # Survey metadata
        surveys_el = ET.SubElement(ET.SubElement(root, "surveys"), "rows")
        row = ET.SubElement(surveys_el, "row")
        _sub(row, "sid", survey.metadata.get("ls_sid", survey.id))
        _sub(row, "surveyls_title", survey.title)
        _sub(row, "surveyls_description", survey.description)

        # Groups
        groups_rows = ET.SubElement(ET.SubElement(root, "groups"), "rows")
        # Questions
        questions_rows = ET.SubElement(ET.SubElement(root, "questions"), "rows")
        # Answers
        answers_rows = ET.SubElement(ET.SubElement(root, "answers"), "rows")

        for section in survey.sections:
            gid = section.metadata.get("ls_gid", section.id)
            grow = ET.SubElement(groups_rows, "row")
            _sub(grow, "gid", str(gid))
            _sub(grow, "group_name", section.title)
            _sub(grow, "description", section.description)
            _sub(grow, "group_order", str(section.order))

            for question in section.questions:
                qid = question.metadata.get("ls_qid", question.id)
                ls_type = question.metadata.get("ls_type") or _INTERNAL_TO_LS_TYPE.get(
                    question.type, "T"
                )

                qrow = ET.SubElement(questions_rows, "row")
                _sub(qrow, "qid", str(qid))
                _sub(qrow, "gid", str(gid))
                _sub(qrow, "type", ls_type)
                _sub(qrow, "question", question.text)
                _sub(qrow, "mandatory", "Y" if question.required else "N")
                _sub(qrow, "question_order", str(question.order + 1))

                for opt in question.answer_options:
                    arow = ET.SubElement(answers_rows, "row")
                    _sub(arow, "qid", str(qid))
                    code = opt.metadata.get("ls_code", opt.id)
                    _sub(arow, "code", str(code))
                    _sub(arow, "answer", opt.text)
                    _sub(arow, "sortorder", "0")

        ET.indent(root, space="  ")
        return ET.tostring(root, encoding="unicode", xml_declaration=True)

    # ------------------------------------------------------------------
    # Submit
    # ------------------------------------------------------------------

    def submit_responses(self, survey_id: str, responses: list[Response]) -> None:
        """Submit responses to LimeSurvey via the RemoteControl 2 JSON-RPC API.

        Authenticates with get_session_key, fetches the question/group mapping via
        list_questions to build correct SGQA field keys, calls add_response, then
        releases the session with release_session_key.

        Args:
            survey_id: The LimeSurvey survey ID (numeric sid as string).
            responses: Responses to submit. Each response must have ``ls_qid`` set
                in its metadata (populated automatically when the survey was imported
                via this adapter).

        Raises:
            ValueError: If API credentials are not configured, or if a response is
                missing ``ls_qid`` metadata required to build the SGQA field key.
            RuntimeError: If authentication, the list_questions call, or submission fails.
        """
        if not self._api_url or not self._username or not self._password:
            raise ValueError(
                "LimeSurvey API URL, username, and password must be set to submit responses."
            )

        session_key = self._get_session_key()
        try:
            gid_map = self._fetch_question_gid_map(session_key, survey_id)
            response_data = _responses_to_ls_format(responses, survey_id, gid_map)
            result = self._rpc_call("add_response", [session_key, survey_id, response_data])
            if isinstance(result, dict) and result.get("status"):
                raise RuntimeError(f"LimeSurvey add_response failed: {result['status']}")
            logger.info("Submitted %d responses to LimeSurvey survey %s", len(responses), survey_id)
        finally:
            self._release_session_key(session_key)

    def _get_session_key(self) -> str:
        result = self._rpc_call("get_session_key", [self._username, self._password])
        if isinstance(result, dict) and result.get("status"):
            raise RuntimeError(f"LimeSurvey authentication failed: {result['status']}")
        return result

    def _fetch_question_gid_map(self, session_key: str, survey_id: str) -> dict[str, str]:
        """Return a mapping of qid → gid for all questions in the survey.

        Calls list_questions via the RemoteControl 2 API so that submit_responses
        can build correct SGQA field keys without relying on locally cached metadata.

        Args:
            session_key: Active RemoteControl 2 session key.
            survey_id: The LimeSurvey survey ID (numeric sid as string).

        Returns:
            dict mapping question id strings to group id strings.

        Raises:
            RuntimeError: If the API returns an unexpected response shape.
        """
        result = self._rpc_call("list_questions", [session_key, survey_id])
        if not isinstance(result, list):
            raise RuntimeError(
                f"list_questions returned unexpected result for survey {survey_id}: {result!r}"
            )
        return {str(q["id"]): str(q["gid"]) for q in result if "id" in q and "gid" in q}

    def _release_session_key(self, session_key: str) -> None:
        try:
            self._rpc_call("release_session_key", [session_key])
        except Exception:  # noqa: BLE001
            logger.warning("Failed to release LimeSurvey session key — continuing")

    def _rpc_call(self, method: str, params: list[Any]) -> Any:
        """Execute a RemoteControl 2 JSON-RPC call."""
        assert self._api_url is not None  # enforced by submit_responses credential check
        payload = {"method": method, "params": params, "id": 1}
        try:
            resp = requests.post(
                self._api_url,
                data=json.dumps(payload),
                headers={"content-type": "application/json"},
                timeout=30,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(f"LimeSurvey RPC call '{method}' failed: {exc}") from exc

        body = resp.json()
        if body.get("error"):
            raise RuntimeError(f"LimeSurvey RPC error in '{method}': {body['error']}")
        return body.get("result")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def questions_by_qid_in_group(
    questions_by_gid: dict[str, list[dict[str, Any]]], gid: str
) -> list[dict[str, Any]]:
    """Return the list of question metadata for a given group ID."""
    return questions_by_gid.get(gid, [])


def _sub(parent: Element, tag: str, text: str) -> Element:
    """Create a sub-element with text content."""
    el = ET.SubElement(parent, tag)
    el.text = text
    return el


def _responses_to_ls_format(
    responses: list[Response],
    survey_id: str,
    gid_map: dict[str, str],
) -> dict[str, Any]:
    """Convert internal Response objects to LimeSurvey add_response field dict.

    LimeSurvey expects a flat dict keyed by SGQA field codes:
    ``<sid>X<gid>X<qid>`` for scalar answers, ``<sid>X<gid>X<qid>[<code>]``
    for multiple-choice sub-fields.

    Args:
        responses: Responses to convert. Each must have ``ls_qid`` in metadata.
        survey_id: The LimeSurvey survey ID (sid) used as the S component of the key.
        gid_map: Mapping of qid → gid obtained from list_questions.

    Raises:
        ValueError: If a response's ls_qid is not present in gid_map.
    """
    data: dict[str, Any] = {}
    for resp in responses:
        qid = str(resp.metadata.get("ls_qid", resp.question_id))
        gid = gid_map.get(qid)
        if gid is None:
            raise ValueError(
                f"Cannot build SGQA key for question '{resp.question_id}': "
                f"qid '{qid}' not found in survey {survey_id}. "
                "Ensure ls_qid is set in response metadata and matches a question in this survey."
            )
        prefix = f"{survey_id}X{gid}X{qid}"
        value = resp.answer_value
        if isinstance(value, list):
            # multiple_choice or ranking: LimeSurvey expects separate fields per option
            for item in value:
                data[f"{prefix}[{item}]"] = "Y"
        else:
            data[prefix] = str(value) if value is not None else ""
    return data
