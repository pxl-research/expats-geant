# Change: Implement M-Autofill REST API & FastAPI Integration

## Why

The RAG pipeline and audit logging (3.1–3.2) are complete but internal—users and institutional systems cannot access them without REST API endpoints. This change exposes M-Autofill's capabilities via a clean, authenticated REST API that integrates with the session/auth middleware, enabling real users to upload documents, request suggestions, download audit reports, and manage their sessions.

## What Changes

- **REST API Endpoints:** Document upload, answer suggestion, audit report retrieval, session cleanup, consent/privacy disclosure
- **FastAPI Framework:** Async HTTP server with OpenAPI documentation, error handling, and request validation
- **Session/Auth Middleware:** Implicit session creation from JWT tokens, automatic session context binding
- **Docker Container:** M-Autofill service containerized with dependencies (ChromaDB, Python runtime)
- **No schema changes:** API schema is defined by endpoint contracts; data models unchanged from 3.1–3.2

**Breaking Changes:** None (new service)

## Impact

- **Affected specs:**

  - `specs/answer-suggestion/spec.md` (already complete from 3.1; no changes)
  - `specs/audit-compliance/spec.md` (already complete from 3.2; no changes)
  - `specs/auth-security/spec.md` (middleware integration; existing JWT already required)

- **Affected code:**

  - `m_autofill/api.py` (new; FastAPI application and endpoint definitions)
  - `m_shared/auth/middleware.py` (existing; session injection middleware)
  - `Dockerfile` (new; containerization)
  - `docker-compose.yml` (new or updated; M-Autofill service definition)

- **New dependencies:** FastAPI, uvicorn (already in requirements.txt likely)

## Timeline

- **Estimated duration:** 2–3 weeks (Mar Week 3 – Apr Week 1)
- **Blockers:** Must wait for 3.1 and 3.2 to be complete and tested

## Implementation Approach

1. Design REST API contracts (request/response schemas)
2. Implement FastAPI application with error handling and validation
3. Implement endpoint handlers (upload, suggest, audit, cleanup, privacy)
4. Integrate session/auth middleware for implicit session management
5. Write comprehensive integration tests for full user flows
6. Manual testing: end-to-end session flow via HTTP calls
7. Docker containerization and deployment verification
