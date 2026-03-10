"""M-Chat: questionnaire design co-pilot for survey administrators."""

from m_chat.style import build_style_context, extract_style_document, summarise_style_rules
from m_chat.suggestion_engine import SuggestionResult, suggest_question
from m_chat.tagging_engine import suggest_tags
from m_chat.validation_engine import ValidationIssue, validate_question, validate_survey

__all__ = [
    "suggest_question",
    "SuggestionResult",
    "validate_question",
    "validate_survey",
    "ValidationIssue",
    "suggest_tags",
    "extract_style_document",
    "summarise_style_rules",
    "build_style_context",
]
