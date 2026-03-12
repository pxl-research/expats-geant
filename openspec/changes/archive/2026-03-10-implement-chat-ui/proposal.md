# Change: Implement M-Chat UI

## Why

The conversational M-Chat API (`implement-chat-api`) needs a pilot-facing interface.
Without a UI, the iterative questionnaire authoring flow is not accessible to non-technical
survey administrators during the pilot phase.

## What Changes

- New `m_chat_ui/` service: HTMX-based web interface for the M-Chat conversational API
- Landing page: list active sessions (resume) or start a new one
- Style setup page: language selector, optional free-text preferences, optional style guide
  document upload — shown once after session creation, skippable
- Chat page: message input, assistant response display, live survey preview sidebar,
  language/style indicator with edit link
- Export page: platform selector, export to file or push to platform via adapter create
- Docker container for `m_chat_ui`, registered in `docker-compose.yml`

## Impact

- Affected specs: new `m-chat-ui` capability
- Affected code: new `m_chat_ui/` package, `docker-compose.yml`
- Depends on: `implement-chat-api`
- No changes to M-Chat API or engines
