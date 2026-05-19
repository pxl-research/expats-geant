"""Unit tests for shape_ui.api_client error handling.

Specifically covers `_raise_for_status`'s behaviour against the three shapes of
`detail` the Shape API can produce: string (legacy hand-rolled details),
FastAPI's structured validation-error list (from strongly-typed-models 422s),
and unexpected/missing detail shapes.
"""

import json

import httpx
import pytest

from shape_ui.api_client import APIError, _format_validation_errors, _raise_for_status


def _response(
    status_code: int, body: dict | None = None, text: str | None = None
) -> httpx.Response:
    """Build an httpx.Response with the supplied JSON or text body."""
    if body is not None:
        return httpx.Response(status_code=status_code, content=json.dumps(body).encode())
    return httpx.Response(status_code=status_code, content=(text or "").encode())


class TestRaiseForStatusStringDetail:
    def test_string_detail_passes_through(self):
        resp = _response(403, {"detail": "Session not found or access denied"})
        with pytest.raises(APIError) as exc:
            _raise_for_status(resp)
        assert exc.value.status_code == 403
        assert exc.value.detail == "Session not found or access denied"


class TestRaiseForStatusStructuredDetail:
    def test_structured_422_detail_flattened(self):
        resp = _response(
            422,
            {
                "detail": [
                    {
                        "type": "missing",
                        "loc": ["body", "survey", "title"],
                        "msg": "Field required",
                        "input": {},
                    },
                    {
                        "type": "string_too_short",
                        "loc": ["body", "survey", "sections", 0, "id"],
                        "msg": "String should have at least 1 character",
                        "input": "",
                    },
                ]
            },
        )
        with pytest.raises(APIError) as exc:
            _raise_for_status(resp)

        # No raw dict/list repr leakage in the user-facing message
        assert "{" not in exc.value.detail
        assert "[" not in exc.value.detail
        # Both validation errors present and readable
        assert "survey.title: Field required" in exc.value.detail
        assert "survey.sections.0.id: String should have at least 1 character" in exc.value.detail
        # Joined with semicolons
        assert exc.value.detail.count(";") == 1

    def test_body_prefix_stripped(self):
        formatted = _format_validation_errors(
            [{"type": "missing", "loc": ["body", "survey", "title"], "msg": "Field required"}]
        )
        assert formatted == "survey.title: Field required"

    def test_non_body_loc_kept_verbatim(self):
        """`loc` outside request-body (e.g. query params) keeps its first element."""
        formatted = _format_validation_errors(
            [{"type": "missing", "loc": ["query", "session_id"], "msg": "Field required"}]
        )
        assert formatted == "query.session_id: Field required"

    def test_empty_loc_renders_as_root(self):
        formatted = _format_validation_errors(
            [{"type": "invalid_type", "loc": [], "msg": "Bad input"}]
        )
        assert formatted == "(root): Bad input"

    def test_empty_list_returns_fallback(self):
        assert _format_validation_errors([]) == "validation error"


class TestRaiseForStatusFallbacks:
    def test_unexpected_detail_shape_falls_back_to_repr(self):
        resp = _response(500, {"detail": {"weird": "object"}})
        with pytest.raises(APIError) as exc:
            _raise_for_status(resp)
        # repr is acceptable for unexpected shapes; assertion only checks no crash
        assert isinstance(exc.value.detail, str)
        assert "weird" in exc.value.detail

    def test_missing_detail_key_uses_text_fallback(self):
        resp = _response(500, {"error": "x"})
        with pytest.raises(APIError) as exc:
            _raise_for_status(resp)
        # Body had no `detail`; .get returns resp.text (the JSON-encoded body)
        assert isinstance(exc.value.detail, str)
        assert "error" in exc.value.detail

    def test_non_json_body_uses_text(self):
        resp = _response(502, text="Bad Gateway")
        with pytest.raises(APIError) as exc:
            _raise_for_status(resp)
        assert exc.value.detail == "Bad Gateway"

    def test_2xx_responses_dont_raise(self):
        resp = _response(200, {"ok": True})
        # Should be a no-op
        _raise_for_status(resp)
