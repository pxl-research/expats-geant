"""LimeSurvey platform adapter.

Handles import/export of LimeSurvey Structure (LSS) XML files and response
submission via the LimeSurvey RemoteControl 2 JSON-RPC API.

LSS format overview:
    - Root element: <document> containing <surveys>, <groups>, <questions>,
      <subquestions> (LS 6+), <answers>
    - surveys/rows/row: survey-level metadata (sid, surveyls_title, surveyls_description)
    - groups/rows/row: question groups (gid, group_name, description, group_order)
    - questions/rows/row: questions (qid, gid, type, question, mandatory)
    - subquestions/rows/row: option rows for multi-answer questions (M, P) and
      array sub-questions. Older LSS exports inline these into <questions> with
      a non-zero parent_qid; both shapes are accepted on import.
    - answers/rows/row: answer options for radio/dropdown choice questions
      (L, O, !, ...) keyed by qid + code.

Submission keying (SGQA):
    LimeSurvey's RemoteControl 2 add_response expects field keys of the form
    ``{sid}X{gid}X{qid}`` for scalar answers and ``{sid}X{gid}X{qid}{title}``
    (sub-question title appended, no brackets) for multi-answer questions.

LimeSurvey question types mapped to internal QuestionType:
    L, O, !  → single_choice  (radio list, list with comment, list dropdown)
    M        → multiple_choice
    T, S, U  → open_ended     (long/short/huge text)
    R        → ranking
    N        → slider         (Numerical input — mapped to slider with no range)
"""

import base64
import json
import logging
import uuid
from typing import Any
from xml.etree import ElementTree as ET
from xml.etree.ElementTree import Element

import defusedxml.ElementTree as defused_ET
import requests

from m_shared.adapters.base import ResponseExport, SurveyAdapter
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
    "X": QuestionType.DESCRIPTIVE,
}

# DBVersion stamped into exported LSS documents. Chosen high enough that
# LimeSurvey's importer skips all back-compat shims (lines guarded by
# `iDBVersion < 145 / < 156 / < 170`). Matches the current LS 6.17.x line;
# LS 5 accepts higher-than-known DBVersions without complaint.
_LS_DB_VERSION = "651"

# Type codes that require a per-question get_question_properties call on the
# fetch_survey path: choice types need answeroptions; slider types need
# attributes (min_num, max_num, slider_accuracy). Others (text, M/P, ranking,
# descriptive) do not.
_NEEDS_QUESTION_DETAILS: frozenset[str] = frozenset({"L", "O", "!", "1", "5", "N", "K"})

# Internal QuestionType → LimeSurvey type code (for export)
_INTERNAL_TO_LS_TYPE: dict[QuestionType, str] = {
    QuestionType.SINGLE_CHOICE: "L",
    QuestionType.MULTIPLE_CHOICE: "M",
    QuestionType.OPEN_ENDED: "T",
    QuestionType.RANKING: "R",
    QuestionType.SLIDER: "N",
    QuestionType.DESCRIPTIVE: "X",
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
        return {"import", "export", "submit", "create", "api_create", "responses_export"}

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
        sub_questions_by_parent = self._parse_sub_questions(root)

        sections: list[Section] = []
        for gid, group_meta in groups.items():
            raw_questions = questions_by_qid_in_group(questions_by_gid, gid)
            questions: list[Question] = []
            for q_meta in raw_questions:
                question = self._build_question(q_meta, answers_by_qid, sub_questions_by_parent)
                if question is not None:
                    questions.append(question)

            sections.append(
                Section(
                    id=f"grp_{gid}",
                    title=group_meta["title"],
                    description=group_meta["description"],
                    questions=questions,
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
        """Extract survey-level metadata from the LSS root element.

        Title/description are read from ``<surveys_languagesettings>/rows/row``
        first (LimeSurvey's canonical location) and from ``<surveys>/rows/row``
        as a fallback for hand-written or older test fixtures.
        """
        row = root.find(".//surveys/rows/row")
        if row is None:
            raise ValueError("LSS XML missing <surveys> section")

        sid = _text(row.find("sid")) or str(uuid.uuid4())
        ls_row = root.find(".//surveys_languagesettings/rows/row")
        title = (
            (_text(ls_row.find("surveyls_title")) if ls_row is not None else "")
            or _text(row.find("surveyls_title"))
            or "Untitled Survey"
        )
        description = (
            (_text(ls_row.find("surveyls_description")) if ls_row is not None else "")
            or _text(row.find("surveyls_description"))
            or ""
        )

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

    def _parse_sub_questions(self, root: Element) -> dict[str, list[dict[str, Any]]]:
        """Return dict of parent_qid → list of sub-question option metadata.

        Collects rows from both ``<subquestions>/rows/row`` (LS 6+ format) and
        ``<questions>/rows/row`` entries with non-zero ``parent_qid`` (older /
        inline format). The ``code`` field maps to LimeSurvey's ``title`` column
        — that is the suffix used in SGQA field keys at submit time.
        """
        by_parent: dict[str, list[dict[str, Any]]] = {}

        def _collect(row: Element) -> None:
            parent_qid = _text(row.find("parent_qid"))
            if not parent_qid or parent_qid == "0":
                return
            title = _text(row.find("title"))
            if not title:
                return
            by_parent.setdefault(parent_qid, []).append(
                {
                    "code": title,
                    "text": _text(row.find("question")) or title,
                    "order": int(_text(row.find("question_order")) or "0"),
                }
            )

        for row in root.findall(".//subquestions/rows/row"):
            _collect(row)
        for row in root.findall(".//questions/rows/row"):
            _collect(row)

        for parent in by_parent:
            by_parent[parent].sort(key=lambda r: r["order"])
        return by_parent

    def _build_question(
        self,
        q_meta: dict[str, Any],
        answers_by_qid: dict[str, list[dict[str, Any]]],
        sub_questions_by_parent: dict[str, list[dict[str, Any]]],
    ) -> Question | None:
        """Convert raw question metadata (from LSS XML) into an internal Question."""
        ls_type = q_meta["type"]
        qid = q_meta["qid"]
        if ls_type in ("M", "P"):
            raw_options = sub_questions_by_parent.get(qid, [])
        else:
            raw_options = answers_by_qid.get(qid, [])
        extra = q_meta.get("extra", {})
        extra_metadata = dict(extra)
        if "title" in extra and extra["title"]:
            # Surface the question's user-defined code under a stable key so
            # downstream code (responses export) does not depend on the raw XML
            # field name leaking through.
            extra_metadata["ls_qcode"] = extra["title"]
        return _question_from_meta(
            ls_type=ls_type,
            qid=qid,
            text=q_meta["text"],
            mandatory=q_meta["mandatory"],
            options=raw_options,
            attributes=extra,
            extra_metadata=extra_metadata,
        )

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_survey(self, survey: Survey) -> str:
        """Serialize an internal Survey to LimeSurvey LSS XML format.

        Emits the envelope LimeSurvey's importer requires
        (``LimeSurveyDocType``, ``DBVersion``, ``languages``) and places the
        survey title/description in ``<surveys_languagesettings>`` where LS
        actually reads them. Optional l10n blocks (``question_l10ns``,
        ``group_l10ns``, ``answer_l10ns``) are intentionally omitted —
        LimeSurvey falls back to reading text directly from the main rows
        when those blocks are absent, which keeps our document small and
        single-language.

        Args:
            survey: The survey to serialize.

        Returns:
            str: LSS XML string suitable for import into LimeSurvey 5+/6+.
        """
        sid = survey.metadata.get("ls_sid", survey.id)
        language = survey.metadata.get("language", "en")

        root = ET.Element("document")
        _sub(root, "LimeSurveyDocType", "Survey")
        _sub(root, "DBVersion", _LS_DB_VERSION)
        languages_el = ET.SubElement(root, "languages")
        _sub(languages_el, "language", language)

        surveys_rows = ET.SubElement(ET.SubElement(root, "surveys"), "rows")
        survey_row = ET.SubElement(surveys_rows, "row")
        _sub(survey_row, "sid", str(sid))
        _sub(survey_row, "language", language)
        _sub(survey_row, "active", "N")

        ls_rows = ET.SubElement(ET.SubElement(root, "surveys_languagesettings"), "rows")
        ls_row = ET.SubElement(ls_rows, "row")
        _sub(ls_row, "surveyls_survey_id", str(sid))
        _sub(ls_row, "surveyls_language", language)
        _sub(ls_row, "surveyls_title", survey.title)
        _sub(ls_row, "surveyls_description", survey.description)

        groups_rows = ET.SubElement(ET.SubElement(root, "groups"), "rows")
        questions_rows = ET.SubElement(ET.SubElement(root, "questions"), "rows")
        sub_questions_rows = ET.SubElement(ET.SubElement(root, "subquestions"), "rows")
        answers_rows = ET.SubElement(ET.SubElement(root, "answers"), "rows")

        sub_qid_counter = 1_000_000
        synthetic_qid_counter = 100_000
        synthetic_gid_counter = 10_000
        question_title_counter = 0
        for group_order, section in enumerate(survey.sections):
            ls_gid = section.metadata.get("ls_gid")
            if ls_gid is None or not str(ls_gid).isdigit():
                synthetic_gid_counter += 1
                gid = synthetic_gid_counter
            else:
                gid = int(ls_gid)
            grow = ET.SubElement(groups_rows, "row")
            _sub(grow, "gid", str(gid))
            _sub(grow, "sid", str(sid))
            _sub(grow, "language", language)
            _sub(grow, "group_name", section.title)
            _sub(grow, "description", section.description)
            _sub(grow, "group_order", str(group_order))

            for question_order, question in enumerate(section.questions, start=1):
                ls_qid = question.metadata.get("ls_qid")
                if ls_qid is None or not str(ls_qid).isdigit():
                    synthetic_qid_counter += 1
                    qid = synthetic_qid_counter
                else:
                    qid = int(ls_qid)
                ls_type = question.metadata.get("ls_type") or _INTERNAL_TO_LS_TYPE.get(
                    question.type, "T"
                )
                question_title_counter += 1
                title = question.metadata.get("ls_title") or f"Q{question_title_counter}"

                qrow = ET.SubElement(questions_rows, "row")
                _sub(qrow, "qid", str(qid))
                _sub(qrow, "sid", str(sid))
                _sub(qrow, "gid", str(gid))
                _sub(qrow, "language", language)
                _sub(qrow, "title", str(title))
                _sub(qrow, "type", ls_type)
                _sub(qrow, "question", question.text)
                _sub(qrow, "mandatory", "Y" if question.required else "N")
                _sub(qrow, "question_order", str(question_order))
                _sub(qrow, "parent_qid", "0")

                options_go_to_subquestions = ls_type in ("M", "P")
                for opt_order, opt in enumerate(question.answer_options, start=1):
                    code = opt.metadata.get("ls_code", opt.id)
                    if options_go_to_subquestions:
                        sub_qid_counter += 1
                        srow = ET.SubElement(sub_questions_rows, "row")
                        _sub(srow, "qid", str(sub_qid_counter))
                        _sub(srow, "parent_qid", str(qid))
                        _sub(srow, "sid", str(sid))
                        _sub(srow, "gid", str(gid))
                        _sub(srow, "language", language)
                        _sub(srow, "type", "T")
                        _sub(srow, "title", str(code))
                        _sub(srow, "question", opt.text)
                        _sub(srow, "question_order", str(opt_order))
                    else:
                        arow = ET.SubElement(answers_rows, "row")
                        _sub(arow, "qid", str(qid))
                        _sub(arow, "language", language)
                        _sub(arow, "code", str(code))
                        _sub(arow, "answer", opt.text)
                        _sub(arow, "sortorder", str(opt_order))

        ET.indent(root, space="  ")
        return ET.tostring(root, encoding="unicode", xml_declaration=True)

    # ------------------------------------------------------------------
    # Submit
    # ------------------------------------------------------------------

    def create_survey(self, survey: Survey) -> str:
        """Push a survey to LimeSurvey by importing it as LSS.

        Builds an LSS XML representation via :meth:`export_survey` and pushes
        it in a single ``import_survey`` RPC call. LimeSurvey 6 removed the
        old ``add_question`` incremental path, so this is now the canonical
        create-from-scratch route (and works on LS 5+ as well).

        Args:
            survey: The survey to create on the platform.

        Returns:
            Platform-assigned survey ID as string.

        Raises:
            ValueError: If API credentials are not configured.
            RuntimeError: If the import_survey RPC call fails.
        """
        self._require_credentials("create surveys")
        lss_xml = self.export_survey(survey)
        payload = base64.b64encode(lss_xml.encode("utf-8")).decode("ascii")
        session_key = self._get_session_key()
        try:
            result = self._rpc_ok(
                "import_survey",
                [session_key, payload, "lss", survey.title],
            )
        finally:
            self._release_session_key(session_key)
        return str(int(result))

    def fetch_survey(self, survey_id: str) -> Survey:
        """Fetch a survey from LimeSurvey by composing read-only RC2 calls.

        Uses ``get_survey_properties`` + ``list_groups`` + ``list_questions``
        and, for question types that need them, ``get_question_properties``
        with the ``answeroptions`` / ``attributes`` fields. This avoids the
        ``export_survey`` RPC method which was removed in LimeSurvey 6.

        Args:
            survey_id: The LimeSurvey survey ID (numeric sid as string).

        Returns:
            Survey: The parsed survey.

        Raises:
            ValueError: If API credentials are not configured.
            RuntimeError: If any RPC call fails.
        """
        self._require_credentials("fetch surveys")
        sid_int = int(survey_id)
        session_key = self._get_session_key()
        try:
            survey_props = self._rpc_ok("get_survey_properties", [session_key, sid_int])
            language = survey_props.get("language") or "en"
            language_props = self._fetch_language_properties(session_key, sid_int)
            groups = self._rpc_ok("list_groups", [session_key, sid_int, language])
            questions = self._rpc_ok("list_questions", [session_key, sid_int, None, language])
            details = self._fetch_question_details(session_key, questions, language)
        finally:
            self._release_session_key(session_key)
        return _assemble_survey_from_rpc(
            survey_id=survey_id,
            survey_props={**survey_props, **language_props},
            groups=groups,
            questions=questions,
            details=details,
        )

    def _fetch_language_properties(self, session_key: str, sid_int: int) -> dict[str, Any]:
        """Return the language-scoped survey settings (title, description).

        These live in a separate table from ``get_survey_properties`` and are
        retrieved via ``get_language_properties``. Returns an empty dict on
        any RPC failure — the title fallback in ``_assemble_survey_from_rpc``
        still produces a usable Survey.
        """
        try:
            return self._rpc_ok(
                "get_language_properties",
                [
                    session_key,
                    sid_int,
                    ["surveyls_title", "surveyls_description"],
                ],
            )
        except RuntimeError as exc:
            logger.warning(
                "get_language_properties failed for survey %s; "
                "falling back to default title: %s",
                sid_int,
                exc,
            )
            return {}

    def submit_responses(self, survey_id: str, responses: list[Response]) -> None:
        """Submit responses to LimeSurvey via the RemoteControl 2 JSON-RPC API.

        Authenticates with get_session_key, fetches the question/group mapping via
        list_questions to build correct SGQA field keys, calls add_response, then
        releases the session with release_session_key.

        Args:
            survey_id: The LimeSurvey survey ID (numeric sid as string).
            responses: Responses to submit. When ``ls_qid`` is present in a
                response's metadata (set automatically on import via this adapter)
                it is used as the question identifier; otherwise ``response.question_id``
                is used as a fallback.

        Raises:
            ValueError: If API credentials are not configured, or if the resolved
                question id for a response is not found in the survey's question map.
            RuntimeError: If authentication, the list_questions call, or submission fails.
        """
        self._require_credentials("submit responses")
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

    def export_responses(self, survey: Survey, responses: list[Response]) -> ResponseExport:
        """Render responses as a VV file consumable by LS's *Import a VV response data file*.

        Emits the exact byte format the LS 6 VV importer expects, verified
        live against LS 6.17.4 by running this output through the admin UI:

        - **TAB-separated** values (LS calls it "VV" — Vertical Verification —
          a format distinct from CSV; the file extension is ``.csv`` by LS
          convention but the separator is ``\\t``).
        - **Two header rows**:
            - Row 1 — human display headers (column display labels,
              ignored by the importer but expected to be present).
            - Row 2 — column codes the importer maps to survey fields:
              ``id, token, submitdate, lastpage, startlanguage, seed, startdate,
              datestamp`` followed by one column per top-level question
              (``ls_qcode``) and one column per ``M``/``P`` sub-question
              keyed ``{qcode}_{sub_qcode}`` (UNDERSCORE separator, no brackets).
        - Data rows: one per response. Empty values use the literal
          ``{question_not_shown}`` marker; multi-choice selected cells contain
          ``Y``; the ``id`` column is left empty so LS auto-assigns.

        This is one of THREE incompatible LS response-formats:

        =========================  ===================================  ========
        Endpoint                   Column shape                         Brackets
        =========================  ===================================  ========
        RC2 ``add_response``       ``{sid}X{gid}X{qid}{sub_title}``     NO
        CSV export (read-only)     ``{qcode}[{sub_qcode}]``             YES
        VV import (this method)    ``{qcode}_{sub_qcode}``              NO
        =========================  ===================================  ========

        These contracts share no parsing code on the LS side; matching one
        does not imply matching another. We previously emitted the CSV-export
        shape and the importer rejected every column ("No answers could be
        mapped") — the VV import contract above is what actually round-trips.

        Args:
            survey: The internal survey. Per-question metadata MUST include
                ``ls_qcode`` (the question's user-defined ``<title>`` code) for
                column matching to work. Sub-question codes come from
                ``AnswerOption.value`` on M/P questions.
            responses: The respondent's answers. ``answer_value`` is the
                option code for single-choice (e.g. ``"A1"``), a list of
                sub-question codes for multi-choice (e.g. ``["A1", "A3"]``),
                or text/numeric for open-ended.

        Returns:
            ResponseExport with ``media_type="text/tab-separated-values"`` and
            ``filename_suffix="_vv.csv"`` (mirrors LS's own ``vvexport_{sid}.csv``
            naming; the leading underscore is part of the suffix).
        """
        responses_by_qid = {str(r.question_id): r for r in responses}

        display_row: list[str] = [
            '"Response ID"',
            "token",
            '"Date submitted"',
            '"Last page"',
            '"Start language"',
            "Seed",
            '"Date started"',
            '"Date last action"',
        ]
        code_row: list[str] = [
            "id",
            "token",
            "submitdate",
            "lastpage",
            "startlanguage",
            "seed",
            "startdate",
            "datestamp",
        ]
        column_sources: list[tuple[str, str | None]] = [("", None) for _ in code_row]

        for section in survey.sections:
            for question in section.questions:
                qcode = str(
                    question.metadata.get("ls_qcode")
                    or question.metadata.get("ls_qid")
                    or question.id
                )
                if question.type == QuestionType.MULTIPLE_CHOICE and question.answer_options:
                    for opt in question.answer_options:
                        sub_code = str(opt.value) if opt.value is not None else ""
                        display_row.append(f'"{question.text} ({opt.text})"')
                        code_row.append(f"{qcode}_{sub_code}")
                        column_sources.append((question.id, sub_code))
                else:
                    display_row.append(f'"{question.text}"')
                    code_row.append(qcode)
                    column_sources.append((question.id, None))

        out_lines: list[str] = ["\t".join(display_row), "\t".join(code_row)]
        if responses:
            # `responses` is one respondent's per-question answers; emit exactly
            # one data row built from responses_by_qid.
            data_row: list[str] = []
            for col_qid, col_sub_code in column_sources:
                if not col_qid:
                    data_row.append("")
                    continue
                target_resp = responses_by_qid.get(col_qid)
                if target_resp is None or target_resp.answer_value is None:
                    data_row.append("{question_not_shown}")
                    continue
                value = target_resp.answer_value
                if col_sub_code is not None:
                    if isinstance(value, list) and col_sub_code in value:
                        data_row.append("Y")
                    else:
                        data_row.append("{question_not_shown}")
                elif isinstance(value, list):
                    data_row.append('"' + ",".join(str(v) for v in value) + '"')
                else:
                    s = str(value)
                    # Quote values containing whitespace or the TAB separator to
                    # mirror LS's own export quoting heuristic.
                    if any(c in s for c in (" ", "\t", '"', "\n")):
                        s = '"' + s.replace('"', '""') + '"'
                    data_row.append(s)
            # Fixed-prefix defaults: id stays empty so LS auto-assigns;
            # startlanguage must be a real language code; the rest are marked
            # not-shown since the session did not capture them.
            data_row[0] = ""
            for fixed_idx, default in (
                (1, "{question_not_shown}"),
                (2, "{question_not_shown}"),
                (3, "{question_not_shown}"),
                (4, "en"),
                (5, "{question_not_shown}"),
                (6, "{question_not_shown}"),
                (7, "{question_not_shown}"),
            ):
                data_row[fixed_idx] = default
            out_lines.append("\t".join(data_row))

        return ResponseExport(
            content=("\n".join(out_lines) + "\n").encode("utf-8"),
            media_type="text/tab-separated-values; charset=utf-8",
            filename_suffix="_vv.csv",
        )

    def _require_credentials(self, op_label: str) -> None:
        """Guard helper — raise ValueError if API credentials are not configured."""
        if not self._api_url or not self._username or not self._password:
            raise ValueError(
                f"LimeSurvey API URL, username, and password must be set to {op_label}."
            )

    def _get_session_key(self) -> str:
        result = self._rpc_call("get_session_key", [self._username, self._password])
        if isinstance(result, dict) and result.get("status"):
            raise RuntimeError(f"LimeSurvey authentication failed: {result['status']}")
        return result

    def _fetch_question_details(
        self,
        session_key: str,
        questions: list[dict[str, Any]],
        language: str,
    ) -> dict[str, dict[str, Any]]:
        """Fetch get_question_properties for the question types that need it.

        Choice types (``L``, ``O``, ``!``, ``1``, ``5``) need ``answeroptions``;
        slider types (``N``, ``K``) need ``attributes``. Other types (text,
        M/P, ranking, descriptive) don't need a per-question RPC roundtrip.
        """
        details: dict[str, dict[str, Any]] = {}
        for q in questions:
            if str(q.get("parent_qid", "0")) != "0":
                continue
            ls_type = q.get("type", "")
            if ls_type not in _NEEDS_QUESTION_DETAILS:
                continue
            qid = q["qid"]
            details[str(qid)] = self._rpc_ok(
                "get_question_properties",
                [session_key, int(qid), ["answeroptions", "attributes"], language],
            )
        return details

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
        assert self._api_url is not None  # enforced by _require_credentials check
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

    def _rpc_ok(self, method: str, params: list[Any]) -> Any:
        """RPC call that also rejects RC2 ``{"status": "..."}`` failure shapes.

        LimeSurvey RC2 methods that succeed return the result type (int, str,
        list, dict). When they fail they often return a single-key dict
        ``{"status": "Error message"}`` *as the result* rather than setting
        the JSON-RPC ``error`` field. This helper raises ``RuntimeError`` on
        that shape so callers don't need to repeat the check.
        """
        result = self._rpc_call(method, params)
        if isinstance(result, dict) and "status" in result:
            raise RuntimeError(f"LimeSurvey {method} failed: {result['status']}")
        return result


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def questions_by_qid_in_group(
    questions_by_gid: dict[str, list[dict[str, Any]]], gid: str
) -> list[dict[str, Any]]:
    """Return the list of question metadata for a given group ID."""
    return questions_by_gid.get(gid, [])


def _question_from_meta(
    *,
    ls_type: str,
    qid: str,
    text: str,
    mandatory: bool,
    options: list[dict[str, Any]],
    attributes: dict[str, Any],
    extra_metadata: dict[str, Any] | None = None,
) -> Question | None:
    """Build an internal ``Question`` from already-shaped Python dicts.

    Shared by both the LSS-XML path (``_build_question``) and the RC2-RPC
    path (``fetch_survey``) so the type mapping, answer-option construction,
    slider-bound handling, and metadata stamping live in one place.

    Args:
        ls_type: LimeSurvey type code (e.g. ``"L"``, ``"M"``, ``"N"``).
        qid: LimeSurvey question id (string).
        text: Question text.
        mandatory: Whether the question is required.
        options: List of ``{"code": ..., "text": ..., "order": ...}`` dicts.
        attributes: Question attributes (used for slider bounds).
        extra_metadata: Optional extra k/v pairs to stamp into question metadata.
    """
    q_type = _LS_TYPE_MAP.get(ls_type)
    if q_type is None:
        logger.warning(
            "Unsupported LimeSurvey question type '%s' (qid=%s) — skipping",
            ls_type,
            qid,
        )
        return None

    answer_options = [
        AnswerOption(
            id=f"opt_{opt['code']}",
            text=opt["text"],
            value=opt["code"],
            metadata={"ls_code": opt["code"]},
        )
        for opt in options
    ]

    min_val = max_val = step = None
    if q_type == QuestionType.SLIDER:
        min_val = float(attributes.get("min_num", 0) or 0)
        max_val = float(attributes.get("max_num", 100) or 100)
        step = float(attributes.get("slider_accuracy", 1) or 1)

    metadata: dict[str, Any] = {
        "platform": "limesurvey",
        "ls_qid": qid,
        "ls_type": ls_type,
    }
    if extra_metadata:
        metadata.update(extra_metadata)

    return Question(
        id=f"q_{qid}",
        text=text,
        type=q_type,
        answer_options=answer_options,
        required=mandatory,
        min_value=min_val,
        max_value=max_val,
        step=step,
        metadata=metadata,
    )


def _assemble_survey_from_rpc(
    *,
    survey_id: str,
    survey_props: dict[str, Any],
    groups: list[dict[str, Any]],
    questions: list[dict[str, Any]],
    details: dict[str, dict[str, Any]],
) -> Survey:
    """Build a Survey from the dicts returned by the LimeSurvey RC2 API.

    Inputs come from ``get_survey_properties``, ``list_groups``,
    ``list_questions``, and per-question ``get_question_properties`` calls.
    The function does not perform any I/O.
    """
    sub_questions_by_parent: dict[str, list[dict[str, Any]]] = {}
    for q in questions:
        parent = str(q.get("parent_qid", "0"))
        if parent == "0":
            continue
        sub_questions_by_parent.setdefault(parent, []).append(
            {
                "code": q.get("title", ""),
                "text": q.get("question") or q.get("title", ""),
                "order": int(q.get("question_order") or 0),
            }
        )
    for parent in sub_questions_by_parent:
        sub_questions_by_parent[parent].sort(key=lambda r: r["order"])

    questions_by_gid: dict[str, list[dict[str, Any]]] = {}
    for q in questions:
        if str(q.get("parent_qid", "0")) != "0":
            continue
        questions_by_gid.setdefault(str(q.get("gid", "")), []).append(q)
    for gid in questions_by_gid:
        questions_by_gid[gid].sort(key=lambda q: int(q.get("question_order") or 0))

    sections: list[Section] = []
    sorted_groups = sorted(groups, key=lambda g: int(g.get("group_order") or 0))
    for group in sorted_groups:
        gid = str(group.get("gid", ""))
        section_questions: list[Question] = []
        for q in questions_by_gid.get(gid, []):
            qid = str(q["qid"])
            ls_type = q.get("type", "")
            if ls_type in ("M", "P"):
                options = sub_questions_by_parent.get(qid, [])
            else:
                options = _answer_options_from_properties(details.get(qid, {}))
            attributes = _attributes_from_properties(details.get(qid, {}))
            qcode = q.get("title") or ""
            question = _question_from_meta(
                ls_type=ls_type,
                qid=qid,
                text=q.get("question") or f"Question {qid}",
                mandatory=str(q.get("mandatory", "")) in ("Y", "y", "1"),
                options=options,
                attributes=attributes,
                extra_metadata={"ls_qcode": qcode} if qcode else None,
            )
            if question is not None:
                section_questions.append(question)

        sections.append(
            Section(
                id=f"grp_{gid}",
                title=group.get("group_name") or f"Section {gid}",
                description=group.get("description") or "",
                questions=section_questions,
                metadata={"ls_gid": gid},
            )
        )

    sid = str(survey_props.get("sid", survey_id))
    return Survey(
        id=sid,
        title=survey_props.get("surveyls_title") or f"Survey {sid}",
        description=survey_props.get("surveyls_description") or "",
        sections=sections,
        metadata={"platform": "limesurvey", "ls_sid": sid},
    )


def _answer_options_from_properties(props: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract answer options from a get_question_properties response.

    The ``answeroptions`` field is either a dict keyed by code with sub-dicts
    containing ``answer`` and ``order``, or the string ``"No available answer
    options"`` when the question has none.
    """
    raw = props.get("answeroptions")
    if not isinstance(raw, dict):
        return []
    options: list[dict[str, Any]] = []
    for code, data in raw.items():
        if not isinstance(data, dict):
            continue
        options.append(
            {
                "code": code,
                "text": data.get("answer") or code,
                "order": int(data.get("order") or data.get("sortorder") or 0),
            }
        )
    options.sort(key=lambda o: o["order"])
    return options


def _attributes_from_properties(props: dict[str, Any]) -> dict[str, Any]:
    """Extract the attributes dict from a get_question_properties response."""
    attrs = props.get("attributes")
    if isinstance(attrs, dict):
        return attrs
    return {}


def _sub(parent: Element, tag: str, text: str) -> Element:
    """Create a sub-element with text content."""
    el = ET.SubElement(parent, tag)
    el.text = text
    return el


def _sgqa_key(survey_id: str, gid: str, qid: str, suffix: str = "") -> str:
    """Build a LimeSurvey SGQA field key for the RC2 ``add_response`` API.

    Top-level questions use ``{sid}X{gid}X{qid}``; multi-answer sub-fields
    append the sub-question's title directly with NO brackets — the bracketed
    form is silently dropped by ``add_response`` (issue #60). Used only by
    ``submit_responses``; the VV export uses qcode-based columns, not SGQA.
    """
    return f"{survey_id}X{gid}X{qid}{suffix}"


def _responses_to_ls_format(
    responses: list[Response],
    survey_id: str,
    gid_map: dict[str, str],
) -> dict[str, Any]:
    """Convert internal Response objects to LimeSurvey add_response field dict.

    LimeSurvey expects a flat dict keyed by SGQA field codes:
    ``<sid>X<gid>X<qid>`` for scalar answers and
    ``<sid>X<gid>X<qid><sub_title>`` (no brackets — the sub-question's title
    is appended directly) for multi-answer sub-fields. The bracketed form
    LimeSurvey's frontend uses internally is silently dropped by add_response.

    Args:
        responses: Responses to convert. ``ls_qid`` in metadata is used as the
            question identifier when available; falls back to ``response.question_id``.
        survey_id: The LimeSurvey survey ID (sid) used as the S component of the key.
        gid_map: Mapping of qid → gid obtained from list_questions.

    Raises:
        ValueError: If the resolved question id for a response is not found in gid_map.
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
        value = resp.answer_value
        if isinstance(value, list):
            for item in value:
                data[_sgqa_key(survey_id, gid, qid, str(item))] = "Y"
        else:
            data[_sgqa_key(survey_id, gid, qid)] = str(value) if value is not None else ""
    return data
