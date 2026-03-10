# Change: Implement M-Chat API

## Why

With the core engines in place (`implement-chat-engines`), this change exposes them as a
usable service. It delivers two things: a stateless REST API for institutional integrations
(callable without session overhead), and a stateful conversational API for iterative
questionnaire authoring. It also adds survey creation capability to all platform adapters.

## What Changes

- Add `create_survey()` to all platform adapters: LimeSurvey and Qualtrics push via their
  write APIs; SurveyMonkey and QTI fall back to file export
- Stateless REST endpoints (`/import`, `/export`, `/create`): no session required; suitable
  for institutional tools calling M-Chat directly
- Context-aware tool endpoints (`/suggest`, `/validate`, `/tag`): work standalone or with a
  `session_id` for survey-scoped, vocabulary-aware reasoning
- Conversational session API (`/chat/*`): session-scoped iterative authoring; LLM orchestrates
  internal tool calls server-side; includes document upload and style profile management
- Docker container for the M-Chat service

## Impact

- Affected specs: `questionnaire-design` (MODIFIED: Platform Adapter Abstraction, Adapter
  Capability Discovery; ADDED: Stateless Tool API, Context-Aware Tool Endpoints,
  Conversational Session API, Document Upload for Survey Drafting)
- Affected code: `m_shared/adapters/` (create capability on all adapters), new `m_chat/api.py`
- Depends on: `implement-chat-engines`
- No breaking changes to M-Autofill
