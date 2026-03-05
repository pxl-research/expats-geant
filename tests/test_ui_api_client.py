"""Unit tests for m_ui.api_client — all HTTP calls mocked with respx."""

import httpx
import pytest
import respx

from m_ui.api_client import (
    APIError,
    batch_suggest,
    get_capabilities,
    get_survey,
    import_survey_file,
    ingest_document,
    submit_responses,
)

BASE = "http://localhost:8001"
TOKEN = "test-jwt-token"


@pytest.mark.asyncio
@respx.mock
async def test_get_survey_success():
    respx.get(f"{BASE}/surveys/survey-123").mock(
        return_value=httpx.Response(
            200, json={"id": "survey-123", "title": "Test Survey", "sections": []}
        )
    )
    result = await get_survey(TOKEN, "survey-123")
    assert result["id"] == "survey-123"


@pytest.mark.asyncio
@respx.mock
async def test_get_survey_not_found():
    respx.get(f"{BASE}/surveys/missing").mock(
        return_value=httpx.Response(404, json={"detail": "Not found"})
    )
    with pytest.raises(APIError) as exc_info:
        await get_survey(TOKEN, "missing")
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
@respx.mock
async def test_get_capabilities_returns_set():
    respx.get(f"{BASE}/adapters/qsf/capabilities").mock(
        return_value=httpx.Response(200, json=["read", "submit", "write"])
    )
    caps = await get_capabilities(TOKEN, "qsf")
    assert isinstance(caps, set)
    assert "submit" in caps


@pytest.mark.asyncio
@respx.mock
async def test_get_capabilities_api_error():
    respx.get(f"{BASE}/adapters/unknown/capabilities").mock(
        return_value=httpx.Response(422, json={"detail": "Unknown format"})
    )
    with pytest.raises(APIError) as exc_info:
        await get_capabilities(TOKEN, "unknown")
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
@respx.mock
async def test_batch_suggest_returns_list():
    respx.post(f"{BASE}/suggest/batch").mock(
        return_value=httpx.Response(
            200,
            json={
                "assessment_id": "s1",
                "session_id": "sess1",
                "generated_at": "2026-01-01T00:00:00Z",
                "model": "llama",
                "responses": [
                    {
                        "item_id": "q1",
                        "type": "open_ended",
                        "suggestion": "Answer A",
                        "citations": [],
                    }
                ],
            },
        )
    )
    result = await batch_suggest(TOKEN, "sess1", "s1", items=[])
    assert len(result) == 1
    assert result[0]["item_id"] == "q1"


@pytest.mark.asyncio
@respx.mock
async def test_batch_suggest_server_error():
    respx.post(f"{BASE}/suggest/batch").mock(
        return_value=httpx.Response(500, json={"detail": "LLM error"})
    )
    with pytest.raises(APIError) as exc_info:
        await batch_suggest(TOKEN, "sess1", "s1", items=[])
    assert exc_info.value.status_code == 500


@pytest.mark.asyncio
@respx.mock
async def test_submit_responses_success():
    respx.post(f"{BASE}/sessions/sess1/submit").mock(
        return_value=httpx.Response(200, json={"status": "ok"})
    )
    # Should not raise
    await submit_responses(TOKEN, "sess1", {"q_1": "answer"})


@pytest.mark.asyncio
@respx.mock
async def test_submit_responses_error():
    respx.post(f"{BASE}/sessions/sess1/submit").mock(
        return_value=httpx.Response(503, json={"detail": "Platform unavailable"})
    )
    with pytest.raises(APIError) as exc_info:
        await submit_responses(TOKEN, "sess1", {"q_1": "answer"})
    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
@respx.mock
async def test_import_survey_file_returns_survey_id():
    respx.post(f"{BASE}/surveys/import").mock(
        return_value=httpx.Response(200, json={"survey_id": "imported-abc", "warning": None})
    )
    survey_id, warning = await import_survey_file(TOKEN, b"file content", "survey.qsf", "qsf")
    assert survey_id == "imported-abc"
    assert warning is None


@pytest.mark.asyncio
@respx.mock
async def test_import_survey_file_returns_warning():
    respx.post(f"{BASE}/surveys/import").mock(
        return_value=httpx.Response(
            200, json={"survey_id": "imported-abc", "warning": "No questions found."}
        )
    )
    survey_id, warning = await import_survey_file(TOKEN, b"file content", "survey.qsf", "qsf")
    assert survey_id == "imported-abc"
    assert warning == "No questions found."


@pytest.mark.asyncio
@respx.mock
async def test_import_survey_file_bad_format():
    respx.post(f"{BASE}/surveys/import").mock(
        return_value=httpx.Response(400, json={"detail": "Unsupported format"})
    )
    with pytest.raises(APIError) as exc_info:
        await import_survey_file(TOKEN, b"data", "survey.xyz", "xyz")
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
@respx.mock
async def test_ingest_document_success():
    respx.post(f"{BASE}/upload").mock(return_value=httpx.Response(200, json={"status": "success"}))
    # Should not raise
    await ingest_document(TOKEN, "sess1", b"pdf bytes", "doc.pdf")


@pytest.mark.asyncio
@respx.mock
async def test_ingest_document_unsupported_format():
    respx.post(f"{BASE}/upload").mock(
        return_value=httpx.Response(400, json={"detail": "Unsupported file type"})
    )
    with pytest.raises(APIError) as exc_info:
        await ingest_document(TOKEN, "sess1", b"exe bytes", "malware.exe")
    assert exc_info.value.status_code == 400
