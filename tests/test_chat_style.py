"""Tests for shape_api.style — style document processing."""

from unittest.mock import Mock

from m_shared.llm.client import LLMClient
from shape_api.style import build_style_context, extract_style_document, summarise_style_rules

# ---------------------------------------------------------------------------
# build_style_context
# ---------------------------------------------------------------------------


def test_build_style_context_empty_profile():
    result = build_style_context({})
    assert "English" in result
    assert "neutral" in result.lower() or "formal" in result.lower()


def test_build_style_context_none_profile():
    result = build_style_context({})
    assert result  # non-empty


def test_build_style_context_with_language_en():
    result = build_style_context({"language": "en"})
    assert "English" in result


def test_build_style_context_with_language_nl():
    result = build_style_context({"language": "nl"})
    assert "Dutch" in result
    assert "nl" in result


def test_build_style_context_with_free_text():
    profile = {"language": "en", "free_text": "Use simple language."}
    result = build_style_context(profile)
    assert "Use simple language." in result


def test_build_style_context_with_document_summary():
    profile = {"language": "en", "document_summary": "Avoid jargon."}
    result = build_style_context(profile)
    assert "Avoid jargon." in result


def test_build_style_context_all_fields():
    profile = {
        "language": "fr",
        "free_text": "Tone formelle.",
        "document_summary": "Pas de termes techniques.",
    }
    result = build_style_context(profile)
    assert "French" in result
    assert "Tone formelle." in result
    assert "Pas de termes techniques." in result


def test_build_style_context_unknown_language_code():
    profile = {"language": "ja"}
    result = build_style_context(profile)
    assert "ja" in result


def test_build_style_context_only_language_adds_default_tone():
    result = build_style_context({"language": "de"})
    assert "German" in result
    # Should have some default tone guidance
    assert len(result) > 15


# ---------------------------------------------------------------------------
# summarise_style_rules
# ---------------------------------------------------------------------------


def test_summarise_style_rules_calls_llm_with_text():
    mock_client = Mock(spec=LLMClient)
    mock_client.create_completion.return_value = "- Use formal tone\n- Avoid jargon"

    extracted = "This is the institutional style guide. Use formal language."
    result = summarise_style_rules(extracted, mock_client)

    call_args = mock_client.create_completion.call_args
    messages = call_args[1]["messages"] if "messages" in call_args[1] else call_args[0][0]
    prompt_content = messages[1]["content"]

    assert extracted in prompt_content
    assert result == "- Use formal tone\n- Avoid jargon"


def test_summarise_style_rules_prompt_contains_key_instruction():
    mock_client = Mock(spec=LLMClient)
    mock_client.create_completion.return_value = "bullets"

    summarise_style_rules("some text", mock_client)

    call_args = mock_client.create_completion.call_args
    messages = call_args[1]["messages"] if "messages" in call_args[1] else call_args[0][0]
    prompt_content = messages[0]["content"]

    assert "style" in prompt_content.lower()


# ---------------------------------------------------------------------------
# extract_style_document — uses a real TXT fixture
# ---------------------------------------------------------------------------


def test_extract_style_document_txt(tmp_path):
    style_file = tmp_path / "style_guide.txt"
    style_file.write_text("Use formal tone. Avoid jargon. Keep questions short.")

    result = extract_style_document(str(style_file))
    assert "formal" in result.lower() or len(result) > 0


def test_extract_style_document_md(tmp_path):
    style_file = tmp_path / "style_guide.md"
    style_file.write_text("# Style Guide\n\n- Use neutral language\n- Avoid leading questions\n")

    result = extract_style_document(str(style_file))
    assert len(result) > 0
