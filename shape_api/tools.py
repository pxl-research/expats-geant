"""LLM tools available during the Shape chat turn.

Currently exposes a single tool, `get_full_survey`, that returns the full JSON
of the session's draft survey so the LLM can build edits from authoritative
state rather than from the compact summary in the system prompt.
"""

from shape_api.session import load_draft_survey

GET_FULL_SURVEY_TOOL: dict = {
    "type": "function",
    "function": {
        "name": "get_full_survey",
        "description": (
            "Return the full JSON of the current draft survey for this session. "
            "Call this before emitting a <survey_update> block: the compact survey "
            "summary in the system prompt intentionally omits answer options, "
            "types, required flags, numeric ranges, and metadata. Build your "
            "update from the JSON returned here and copy unchanged fields verbatim."
        ),
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}

NO_DRAFT_SENTINEL = '{"survey": null}'


def dispatch_tool_call(name: str, arguments: dict, base_path: str, session_id: str) -> str:
    """Run a chat-turn tool call and return a JSON string result.

    Args:
        name: tool name as advertised in the tool schema
        arguments: parsed JSON arguments from the LLM call (unused for the
            current single-tool surface, but accepted for forward compatibility)
        base_path: session storage root
        session_id: active chat session

    Returns:
        JSON string suitable for use as a `role: "tool"` message content.

    Raises:
        ValueError: if `name` is not a registered tool.
    """
    del arguments  # reserved for future tools
    if name == "get_full_survey":
        survey = load_draft_survey(base_path, session_id)
        if survey is None:
            return NO_DRAFT_SENTINEL
        return survey.model_dump_json()
    raise ValueError(f"Unknown tool: {name}")
