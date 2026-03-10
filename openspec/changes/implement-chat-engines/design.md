## Context

This is the first of three M-Chat changes. It establishes the foundational layer that the
API and UI changes will build on. The overall M-Chat architecture has three layers:

```
[implement-chat-ui]   m_chat_ui  ─────────────────────────────────────────┐
                                                                           │
[implement-chat-api]  Conversational API  (always session-scoped)         │◄─┘
                      POST /chat/{session_id}

                      Context-aware tool endpoints  (session optional)
                      POST /suggest    POST /validate    POST /tag

                      Context-free endpoints  (never need a session)
                      POST /import    POST /export    POST /create

[THIS CHANGE]         Session store + Core engines
                      suggestion_engine.py  validation_engine.py  tagging_engine.py
                      session.py  (draft_survey, tag_vocabulary, style_profile, conversation)
```

This change delivers only the bottom layer. No API endpoints are exposed yet.

## Goals / Non-Goals

- **Goals:** Session helpers, three engines, style profile system, full unit test coverage
- **Non-Goals:** API endpoints (next change), UI (third change), LLM evaluation of output quality

## Session Storage Layout

Reuses `m_shared/session/manager.py` for creation, TTL tracking, and cleanup.
Session type field (`"chat"`) distinguishes M-Chat sessions from M-Autofill sessions.
TTL: 7 days (configurable) — survey design is a multi-day activity.

```
sessions/{session_id}/
├── draft_survey.json       # current Survey object
├── tag_vocabulary.json     # { tag: [question_ids] }
├── style_profile.json      # language + free_text + document_summary + defaults_applied
├── conversation.json       # [ {role, content, timestamp} ]
├── documents/              # content docs (source material for question generation)
│   └── {filename}.chunks.json
└── style_documents/        # institutional style guide docs
    └── {filename}.extracted.txt
```

Default `style_profile.json`:
```json
{
  "language": "en",
  "free_text": "",
  "document_summary": "",
  "defaults_applied": true
}
```

## Decisions

### Suggestion engine
- Accepts `question: Question` and optional `survey_context: Survey | None`
- With context: compact survey JSON summary included in LLM prompt (title, section names,
  existing question texts — no metadata, to stay within token budget)
- Without context: single-question prompt, generic reasoning

### Validation engine
- Two tiers to control cost and determinism:
  1. **Deterministic checks** (no LLM, always run): double-barreled detection (conjunction
     patterns), scale length (< 4 or > 7 options flagged), leading language keyword list,
     Likert label completeness
  2. **LLM-assisted checks** (run when session context available or full survey provided):
     clarity, tone, bias, cross-question consistency
- Rules sourced from `docs/SURVEY_DESIGN_GUIDELINES.md`

### Tagging engine
- Without vocabulary: infers tags from question text alone
- With vocabulary: passes existing tag list to LLM — "prefer reuse over new tags"
- Normalisation: lowercase, strip whitespace, deduplicate before storing
- Vocabulary file updated after every tag call in a session

### Style profile
- Language stored as ISO 639-1 code; passed to LLM as explicit instruction on every call
- Free text and document summary both passed as system context
- Style guide document: MarkItDown extracts text → LLM generates concise summary of style
  rules → summary stored (not full text) to stay within token budget
- If `defaults_applied: true`, the system uses English + neutral formal tone + guidelines
  from `SURVEY_DESIGN_GUIDELINES.md` with no extra user input required

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| LLM prompt grows large for long surveys | Pass compact summary (titles + question texts only) |
| Tag vocabulary drifts (near-duplicate tags) | Normalise before storing; show existing tags prominently in prompt |
| Deterministic validation misses subtle bias | Flag as informational, not blocking; LLM tier catches nuanced issues |
