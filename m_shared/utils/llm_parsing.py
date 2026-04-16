"""Parsing helpers for LLM output."""

import re


def strip_code_fences(text: str) -> str:
    """Strip markdown code fences (```json ... ``` or ``` ... ```) from LLM output.

    Returns the inner content with leading/trailing whitespace removed.
    If no code fences are present, returns the text stripped as-is.
    """
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[1:end]).strip()
    return text


def extract_json_object(text: str) -> str:
    """Extract a JSON object from LLM output that may contain surrounding text.

    Tries strip_code_fences first, then looks for a fenced block anywhere in
    the response, and finally tries to find a raw ``{...}`` JSON object.

    Returns the extracted JSON string, or the original text if no object found.
    """
    # Fast path: entire response is a code fence
    stripped = strip_code_fences(text)
    if stripped != text.strip():
        return stripped

    # Look for a fenced JSON block anywhere in the response
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if fence_match:
        return fence_match.group(1).strip()

    # Look for a raw JSON object (outermost { ... })
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        return brace_match.group(0)

    return text.strip()
