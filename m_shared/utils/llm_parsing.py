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


def _find_balanced_json_objects(text: str) -> list[str]:
    """Find all top-level balanced ``{...}`` substrings in text.

    Tracks brace depth while skipping over braces inside quoted strings, so
    each returned substring is one complete, independently-parseable object.
    """
    objects = []
    depth = 0
    start = None
    in_string = False
    escape = False
    for i, ch in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start is not None:
                objects.append(text[start : i + 1])
    return objects


def extract_json_object(text: str) -> str:
    """Extract a JSON object from LLM output that may contain surrounding text.

    Tries strip_code_fences first, then looks for a fenced block anywhere in
    the response, and finally scans for balanced ``{...}`` objects. Models
    sometimes self-correct mid-response ("wait, let me reconsider...") and
    restate a second, final object — when more than one complete object is
    found, the LAST one is taken as the model's final answer.

    Returns the extracted JSON string, or the original text if no object found.
    """
    # Fast path: entire response is a code fence
    stripped = strip_code_fences(text)
    if stripped != text.strip():
        text = stripped
    else:
        # Look for a fenced JSON block anywhere in the response
        fence_match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
        if fence_match:
            text = fence_match.group(1).strip()

    objects = _find_balanced_json_objects(text)
    if objects:
        return objects[-1]

    return text.strip()
