"""Parsing helpers for LLM output."""


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
