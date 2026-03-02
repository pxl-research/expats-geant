"""QTI 3.0 platform adapter (import/export only).

Handles import and export of QTI 3.0 XML. Response submission is not
supported — QTI is a content interchange format, not a survey runtime.

QTI 3.0 structure used here (single-file, items embedded directly):
    <assessmentTest identifier="…" title="…">
      <testPart identifier="…" navigationMode="linear" submissionMode="individual">
        <assessmentSection identifier="…" title="…" visible="true">
          <assessmentItem identifier="…" title="…">
            <responseDeclaration identifier="RESPONSE" cardinality="…" baseType="…"/>
            <itemBody>
              <!-- one interaction element per question type -->
            </itemBody>
          </assessmentItem>
        </assessmentSection>
      </testPart>
    </assessmentTest>

QTI interaction → internal QuestionType mapping:
    choiceInteraction  cardinality=single   → single_choice
    choiceInteraction  cardinality=multiple → multiple_choice
    extendedTextInteraction / textEntryInteraction → open_ended
    orderInteraction                        → ranking
    sliderInteraction                       → slider

Note: We use a single <testPart> per survey. Multiple testParts are parsed
but collapsed into sequential sections on import.
"""

import logging
import uuid
from xml.etree import ElementTree as ET
from xml.etree.ElementTree import Element

import defusedxml.ElementTree as defused_ET

from m_shared.adapters.base import SurveyAdapter
from m_shared.models.answer_option import AnswerOption
from m_shared.models.question import Question, QuestionType
from m_shared.models.section import Section
from m_shared.models.survey import Survey

logger = logging.getLogger(__name__)

_QTI_NS = "http://www.imsglobal.org/xsd/imsqti_v3p0"
_NS = {"qti": _QTI_NS}

# Register namespace so ET serialises without ns0: prefixes
ET.register_namespace("", _QTI_NS)


# Clark-notation helpers
def _q(local: str) -> str:
    return f"{{{_QTI_NS}}}{local}"


# Interaction tag → (QuestionType, cardinality hint)
_INTERACTION_MAP: dict[str, tuple[QuestionType, str | None]] = {
    "choiceInteraction": (QuestionType.SINGLE_CHOICE, None),  # refined by cardinality
    "extendedTextInteraction": (QuestionType.OPEN_ENDED, None),
    "textEntryInteraction": (QuestionType.OPEN_ENDED, None),
    "orderInteraction": (QuestionType.RANKING, None),
    "sliderInteraction": (QuestionType.SLIDER, None),
}

# Internal type → interaction tag
_TYPE_TO_INTERACTION: dict[QuestionType, str] = {
    QuestionType.SINGLE_CHOICE: "choiceInteraction",
    QuestionType.MULTIPLE_CHOICE: "choiceInteraction",
    QuestionType.OPEN_ENDED: "extendedTextInteraction",
    QuestionType.RANKING: "orderInteraction",
    QuestionType.SLIDER: "sliderInteraction",
}


class QTIAdapter(SurveyAdapter):
    """Adapter for QTI 3.0 format (import/export only).

    Parses and serialises QTI 3.0 XML with embedded assessment items.
    Response submission is not applicable to this format.
    """

    def capabilities(self) -> set[str]:
        return {"import", "export"}

    # ------------------------------------------------------------------
    # Import
    # ------------------------------------------------------------------

    def import_survey(self, raw: str) -> Survey:
        """Parse a QTI 3.0 XML string into an internal Survey.

        Args:
            raw: QTI 3.0 XML content as a string.

        Returns:
            Survey: The parsed survey.

        Raises:
            ValueError: If the XML is malformed or missing the assessmentTest root.
        """
        try:
            root = defused_ET.fromstring(raw)
        except ET.ParseError as exc:
            raise ValueError(f"Invalid QTI XML: {exc}") from exc

        # Accept root with or without namespace
        local = _local(root.tag)
        if local != "assessmentTest":
            raise ValueError(f"Expected <assessmentTest> root, got <{local}>")

        survey_id = root.get("identifier") or str(uuid.uuid4())
        title = root.get("title") or "Untitled Survey"
        description = root.get("toolName") or ""

        sections: list[Section] = []
        order = 0
        for test_part in _iter_children(root, "testPart"):
            for assessment_section in _iter_children(test_part, "assessmentSection"):
                section = _parse_section(assessment_section, order)
                if section is not None:
                    sections.append(section)
                    order += 1

        return Survey(
            id=survey_id,
            title=title,
            description=description,
            sections=sections,
            metadata={"platform": "qti", "qti_identifier": survey_id},
        )

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_survey(self, survey: Survey) -> str:
        """Serialise an internal Survey to QTI 3.0 XML.

        Args:
            survey: The survey to export.

        Returns:
            str: QTI 3.0 XML string with embedded assessment items.
        """
        survey_id = survey.metadata.get("qti_identifier", survey.id)

        root = ET.Element(_q("assessmentTest"))
        root.set("identifier", str(survey_id))
        root.set("title", survey.title)
        if survey.description:
            root.set("toolName", survey.description)

        part = ET.SubElement(root, _q("testPart"))
        part.set("identifier", "part1")
        part.set("navigationMode", "linear")
        part.set("submissionMode", "individual")

        for section in survey.sections:
            sec_el = ET.SubElement(part, _q("assessmentSection"))
            sec_id = section.metadata.get("qti_identifier", section.id)
            sec_el.set("identifier", str(sec_id))
            sec_el.set("title", section.title)
            sec_el.set("visible", "true")

            for question in section.questions:
                _build_item_element(sec_el, question)

        ET.indent(root, space="  ")
        return ET.tostring(root, encoding="unicode", xml_declaration=True)


# ------------------------------------------------------------------
# Import helpers
# ------------------------------------------------------------------


def _local(tag: str) -> str:
    """Strip Clark namespace notation from a tag: {ns}local → local."""
    return tag.split("}")[-1] if "}" in tag else tag


def _iter_children(el: Element, local_name: str):
    """Yield direct children matching local_name (namespace-agnostic)."""
    for child in el:
        if _local(child.tag) == local_name:
            yield child


def _find_first(el: Element, local_name: str) -> Element | None:
    """Return first descendant matching local_name, namespace-agnostic."""
    for child in el.iter():
        if _local(child.tag) == local_name:
            return child
    return None


def _parse_section(section_el: Element, order: int) -> Section | None:
    """Parse an <assessmentSection> element into a Section."""
    sec_id = section_el.get("identifier") or str(uuid.uuid4())
    title = section_el.get("title") or f"Section {order + 1}"

    questions: list[Question] = []
    for item_el in _iter_children(section_el, "assessmentItem"):
        q = _parse_item(item_el)
        if q is not None:
            questions.append(q)

    return Section(
        id=f"sec_{sec_id}",
        title=title,
        description="",
        questions=questions,
        order=order,
        metadata={"qti_identifier": sec_id},
    )


def _parse_item(item_el: Element) -> Question | None:
    """Parse an <assessmentItem> element into a Question."""
    item_id = item_el.get("identifier") or str(uuid.uuid4())
    title = item_el.get("title") or f"Item {item_id}"

    # Locate itemBody
    item_body = _find_first(item_el, "itemBody")
    if item_body is None:
        logger.warning("assessmentItem '%s' has no itemBody — skipping", item_id)
        return None

    # Find the interaction element inside itemBody
    interaction_el = None
    interaction_type = None
    for child in item_body.iter():
        local = _local(child.tag)
        if local in _INTERACTION_MAP:
            interaction_el = child
            interaction_type = local
            break

    if interaction_el is None:
        logger.warning("assessmentItem '%s' has no recognised interaction — skipping", item_id)
        return None

    assert (
        interaction_type is not None
    )  # guaranteed: interaction_el is set iff interaction_type is set
    q_type, _ = _INTERACTION_MAP[interaction_type]

    # Refine choiceInteraction cardinality from responseDeclaration
    if interaction_type == "choiceInteraction":
        resp_decl = _find_first(item_el, "responseDeclaration")
        if resp_decl is not None and resp_decl.get("cardinality") == "multiple":
            q_type = QuestionType.MULTIPLE_CHOICE

    # Extract prompt text
    prompt_el = _find_first(interaction_el, "prompt")
    text = (prompt_el.text or "").strip() if prompt_el is not None else title

    # Parse choices / simpleChoices
    answer_options: list[AnswerOption] = []
    for choice_tag in ("simpleChoice",):
        for choice_el in interaction_el.iter():
            if _local(choice_el.tag) == choice_tag:
                code = choice_el.get("identifier", str(uuid.uuid4()))
                choice_text = (choice_el.text or "").strip() or code
                answer_options.append(
                    AnswerOption(
                        id=f"opt_{code}",
                        text=choice_text,
                        value=code,
                        metadata={"qti_identifier": code},
                    )
                )

    # Slider bounds from sliderInteraction attributes
    min_val = max_val = step = None
    if q_type == QuestionType.SLIDER:
        try:
            min_val = float(interaction_el.get("lowerBound", 0))
            max_val = float(interaction_el.get("upperBound", 100))
            step = float(interaction_el.get("step", 1))
        except (TypeError, ValueError):
            min_val, max_val, step = 0.0, 100.0, 1.0

    return Question(
        id=f"q_{item_id}",
        text=text,
        type=q_type,
        answer_options=answer_options,
        min_value=min_val,
        max_value=max_val,
        step=step,
        metadata={"platform": "qti", "qti_identifier": item_id},
    )


# ------------------------------------------------------------------
# Export helpers
# ------------------------------------------------------------------


def _build_item_element(parent: Element, question: Question) -> None:
    """Append an <assessmentItem> element to parent for the given question."""
    qti_id = question.metadata.get("qti_identifier", question.id)

    item_el = ET.SubElement(parent, _q("assessmentItem"))
    item_el.set("identifier", str(qti_id))
    item_el.set("title", question.text)
    item_el.set("adaptive", "false")
    item_el.set("timeDependent", "false")

    # responseDeclaration
    resp_decl = ET.SubElement(item_el, _q("responseDeclaration"))
    resp_decl.set("identifier", "RESPONSE")
    _BASE_TYPE = {
        QuestionType.OPEN_ENDED: "string",
        QuestionType.SLIDER: "float",
    }
    resp_decl.set("baseType", _BASE_TYPE.get(question.type, "identifier"))
    if question.type == QuestionType.MULTIPLE_CHOICE:
        resp_decl.set("cardinality", "multiple")
    elif question.type in (QuestionType.RANKING, QuestionType.OPEN_ENDED):
        resp_decl.set(
            "cardinality", "ordered" if question.type == QuestionType.RANKING else "single"
        )
    else:
        resp_decl.set("cardinality", "single")

    item_body = ET.SubElement(item_el, _q("itemBody"))
    interaction_tag = _TYPE_TO_INTERACTION[question.type]
    interaction = ET.SubElement(item_body, _q(interaction_tag))
    interaction.set("responseIdentifier", "RESPONSE")
    if question.type in (
        QuestionType.SINGLE_CHOICE,
        QuestionType.MULTIPLE_CHOICE,
        QuestionType.RANKING,
    ):
        interaction.set("shuffle", "false")

    if question.type == QuestionType.SINGLE_CHOICE:
        interaction.set("maxChoices", "1")
    elif question.type == QuestionType.MULTIPLE_CHOICE:
        interaction.set("maxChoices", "0")  # 0 = unlimited in QTI
    elif question.type == QuestionType.SLIDER:
        interaction.set("lowerBound", str(int(question.min_value or 0)))
        interaction.set("upperBound", str(int(question.max_value or 100)))
        interaction.set("step", str(int(question.step or 1)))

    # Prompt
    prompt_el = ET.SubElement(interaction, _q("prompt"))
    prompt_el.text = question.text

    # Choices
    for opt in question.answer_options:
        choice_tag = "simpleChoice" if question.type != QuestionType.RANKING else "simpleChoice"
        choice_el = ET.SubElement(interaction, _q(choice_tag))
        code = str(opt.metadata.get("qti_identifier", opt.value or opt.id))
        choice_el.set("identifier", code)
        choice_el.text = opt.text
