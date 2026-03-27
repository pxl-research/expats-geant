# Change: Align specs with deployed API token, image ingestion, and thinking budget

## Why

Four implemented features are absent from or contradict the current specs. All features
are already deployed; this change is documentation-only (no code changes required).

1. `/dev/token` was removed and replaced by the production `POST /auth/token` endpoint,
   which supports server-to-server auth and anonymous callers via a caller-supplied
   `user_id`. The spec still documents the old endpoint.
2. Image files (jpg/jpeg/png/gif/webp) are accepted and converted to text via LLM before
   ingestion. The spec says "Text, PDF, DOCX formats only".
3. `LLMClient` supports an extended-thinking budget (`thinking_budget` / env var
   `THINKING_BUDGET_TOKENS`). The llm-integration spec has no mention of this.

## What Changes

- **auth-security**: REMOVE `Development Token Generation Endpoint` (endpoint deleted);
  ADD `API Token Endpoint` (`POST /auth/token`, shared secret, rate-limited, supports
  anonymous callers via `user_id`); MODIFY `Environment-Based Configuration` to remove
  stale `/dev/token` references.
- **document-ingestion**: MODIFY `Multi-Format Document Upload` to include all supported
  extensions (including images); ADD `Image-to-Text Conversion` requirement.
- **llm-integration**: ADD `Extended Thinking Budget` requirement; update Notes to
  include `THINKING_BUDGET_TOKENS` and `API_SECRET` env vars.

## Impact

- Affected specs: auth-security, document-ingestion, llm-integration
- Affected code: none — all features already deployed
