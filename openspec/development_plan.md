# Development Plan

This document outlines the phased approach to building Expat-GÉANT from January to June 2026, aligned with the baseline capability specs in `specs/`.

## Project Timeline

- **Start:** January 2026
- **Pilot & Evaluation:** January–April 2026 (PXL + Belnet partners)
- **Demo & Dissemination:** May 2026 (GÉANT TNC)
- **Final Report:** 30 June 2026

## Phase 1: Foundation & Shared Infrastructure (Jan–Feb)

**Goal:** Establish core building blocks for both M-Chat and M-Autofill.

**Deliverables:**

- ✅ [Baseline capability specs](specs/) defined
- ✅ Data models (Survey, Section, Question, Response, Citation, Session) — [specs/data-models](specs/data-models/spec.md)
- ✅ LLM client (OpenRouter integration) — [specs/llm-integration](specs/llm-integration/spec.md)
- ✅ Basic auth (JWT token generation & validation) — [specs/auth-security](specs/auth-security/spec.md)
- ✅ Unit tests for models, LLM client, and auth
- ✅ Development environment setup (requirements.txt, .env example)

**Key Files:**

- ✅ `m_shared/models/*.py` (Survey, Section, Question, AnswerOption, Response, Citation, Session)
- ✅ `m_shared/llm/client.py` (OpenRouter client with retries)
- ✅ `m_shared/auth/jwt_handler.py` (Token creation/validation)
- ✅ `m_shared/auth/validators.py` (Input validation & sanitization)

**Dependencies:** None (foundation layer)

**Success Criteria:**

- ✅ Models serialize/deserialize correctly with validation
- ✅ LLM client successfully calls OpenRouter
- ✅ JWT tokens can be created and validated
- ✅ All unit tests passing (46 tests across auth, validators, models, LLM)

---

## Phase 2: Document Processing & Vector Search (Feb–Mar)

**Goal:** Enable document upload, chunking, and semantic search for M-Autofill.

**Status:** ✅ Phase 2.1 (Document Ingestion) **COMPLETE**

**Deliverables:**

- ✅ Document ingestion pipeline (text extraction, chunking) — [specs/document-ingestion](specs/document-ingestion/spec.md)
  - Multi-format support (PDF, DOCX, TXT, Markdown)
  - Iterative chunking with header/sentence/threshold strategies
  - Metadata preservation (source, chunk_index, position)
  - Fixed infinite loop bug in overlap logic
- ⏳ Vector DB client (ChromaDB wrapper with session isolation) — [specs/vector-db](specs/vector-db/spec.md) — In Progress
- ⏳ Session management & TTL cleanup — Pending
- ✅ Input validation & sanitization (auth-security) — [specs/auth-security](specs/auth-security/spec.md)
  - File size validation (configurable, 50MB default)
  - File type validation (whitelist: .txt, .pdf, .docx, .md)
  - Comprehensive error handling (FileValidationError)
- ✅ Unit tests for chunking, embedding, search — 74 tests, 100% passing
- ✅ Integration test: upload → chunk → search flow

**Key Files (Completed):**

- ✅ `m_autofill/ingest.py` (Upload, parse, chunk via `ingest_files_into_store()`)
- ✅ `m_autofill/validation.py` (File validation with size/type checks)
- ✅ `m_shared/vectordb/utils.py` (Text extraction, chunking algorithms)
- ✅ `tests/test_document_ingestion.py` (13 tests for text extraction)
- ✅ `tests/test_chunking.py` (24 tests for all chunking strategies)
- ✅ `tests/test_validation.py` (22 tests for file validation)
- ✅ `tests/test_metadata.py` (7 tests for metadata preservation)
- ✅ `tests/test_integration_ingestion.py` (8 end-to-end integration tests)

**Test Data:**

- ✅ `tests/test_data/documents/` — Sample files for all supported formats

**Dependencies:** Phase 1 (data models, LLM client)

**Success Criteria (Phase 2.1):**

- ✅ Documents uploaded, parsed, and chunked correctly
- ✅ All chunking strategies respect boundaries (headers, sentences, word boundaries)
- ✅ Session-based isolation validated (using tmp_path per test)
- ✅ File validation working (size, type, existence)
- ✅ Metadata preserved (source, chunk indices, etc.)
- ✅ All unit & integration tests passing (74/74 = 100%)

**Next (Phase 2.2):** Vector DB session isolation & TTL cleanup

**Success Criteria (Phase 2.2):**

- ✅ SessionManager class implemented with JWT-based session IDs
- ✅ Folder-based session isolation (sessions/{session_id}/)
- ✅ TTL tracking with expiration logic
- ✅ Session creation, retrieval, deletion, listing, cleanup methods
- ✅ Integration with ChromaDocumentStore (composition pattern)
- ✅ All unit tests passing (27/27 = 100%)
- ✅ All integration tests passing (8/8 = 100%)
- ✅ Session isolation validated (no cross-session data leakage)
- ✅ Concurrent session handling validated
- ✅ Session middleware for implicit session management (lazy creation on first authenticated request)
- ✅ DELETE /session endpoint for explicit user cleanup
- ✅ All API tests passing (12/12 = 100%)
- ✅ Background cleanup job for expired sessions (cleanup_expired_sessions with 1-year retention for audit reports)

**Phase 2.2 Status:** ✅ **COMPLETE** (except background cleanup job deferred)

**Note:** Sessions are managed implicitly via JWT authentication. No explicit session creation endpoints needed—sessions are created automatically on first authenticated request and cleaned up by background job.

---

## Phase 3: M-Autofill (Answer Suggestion Module) (Mar–Apr)

**Goal:** Complete RAG pipeline with answer suggestions, citations, audit logging, and REST API endpoints.

**Status:** ✅ **PHASE 3 COMPLETE** (All 3 sub-changes finished)

### Change 3.1: `implement-autofill-rag-citations` ✅ **COMPLETE** (Mar, Week 1-2)

**Deliverables:**

- [x] RAG pipeline (semantic retrieval + LLM generation) — [specs/answer-suggestion](specs/answer-suggestion/spec.md)
- [x] Citation system (track sources, metadata, text highlights)
- [x] Unit tests for retrieval, generation, citation formatting

**Key Files:**

- `m_autofill/rag_pipeline.py` (Retrieval, generation, citations) — 392 lines
- `tests/test_rag_pipeline.py` — 31 unit tests
- `tests/test_rag_integration.py` — 8 integration tests

**Dependencies:** Phase 1, Phase 2

**Success Criteria:**

- [x] Suggestions generated with cited sources
- [x] Citations include source metadata (filename, position, timestamp, text excerpt)
- [x] All unit tests passing (31/31 unit tests + 8/8 integration tests)
- [x] 248/248 total tests passing (no regressions)

---

### Change 3.2: `implement-autofill-audit-logging` ✅ **COMPLETE** (Mar, Week 2-3)

**Deliverables:**

- [x] Session audit trail (log uploads, suggestions, user edits) — [specs/audit-compliance](specs/audit-compliance/spec.md)
- [x] Audit report generation (complete session summary with sources)
- [x] Retention policy (auto-delete unclaimed reports after ~1 year)
- [x] Consent/privacy capture at session start
- [x] Unit tests for logging, report structure, retention logic

**Key Files:**

- [x] `m_shared/utils/audit.py` (Audit logging & reports) — 540 lines
- [x] `m_shared/utils/__init__.py` (Package exports)
- [x] `m_autofill/ingest.py` (Upload event logging)
- [x] `m_autofill/rag_pipeline.py` (Suggestion event logging)
- [x] `m_shared/session/manager.py` (Session lifecycle & retention enforcement)
- [x] `tests/test_audit.py` — 25 unit tests
- [x] `tests/test_audit_integration.py` — 8 integration tests

**Dependencies:** Phase 1, Phase 2, 3.1

**Success Criteria:**

- [x] Audit trail captures all session activity (UPLOAD, SUGGEST, EDIT_SUGGESTION, SESSION_START, SESSION_END, CONSENT_ACCEPTED)
- [x] Reports include all suggestions, sources, user edits with timestamps
- [x] Retention policy enforced (1-year auto-delete via \_cleanup_old_reports)
- [x] All unit tests passing (25/25)
- [x] All integration tests passing (7/8 — 1 skipped due to missing API key, structure validated)
- [x] Thread-safe concurrent logging validated
- [x] Session isolation validated (no cross-session data leakage)
- [x] 280/280 total tests passing (no regressions)

---

### Change 3.3: `implement-autofill-api-endpoints` ✅ **COMPLETE** (Jan Week 2)

**Deliverables:**

- [x] REST API endpoints (upload, suggest, audit report retrieval, cleanup)
- [x] FastAPI integration with session/auth middleware
- [x] Integration tests: full user session flow (23/23 tests passing)
- [x] Docker container for M-Autofill service
- [x] docker-compose.yml for deployment

**Key Files:**

- [x] `m_autofill/api.py` (FastAPI endpoints) — 422 lines, 6 endpoints
- [x] `tests/test_session_api.py` — 586 lines, 23 tests
- [x] `Dockerfile` and `docker-compose.yml`
- [x] `m_shared/auth/middleware.py` — Updated public endpoints
- [x] `requirements.txt` — Added python-multipart

**Dependencies:** Phase 1, Phase 2, 3.1, 3.2

**Success Criteria:**

- [x] API endpoints respond correctly (POST /upload, POST /suggest, GET /audit-report, GET /privacy, GET /session/stats, DELETE /session)
- [x] Session isolation & middleware working (JWT-based auth, implicit session creation)
- [x] All integration tests passing (23/23 = 100%)
- [x] Docker container configuration complete
- [ ] Manual testing & citation accuracy review (deferred to Phase 5)

**Phase 3.3 Status:** ✅ **COMPLETE**

**Total Phase 3 Progress:** 3/3 changes complete (RAG pipeline, audit logging, API endpoints)

---

## Phase 4: M-Chat (Questionnaire Design Module) (Feb–Mar)

**Goal:** Complete questionnaire design assistant with validation, suggestions, tagging, and QTI support.

**Deliverables:**

- [ ] Question suggestion engine (LLM-based rewording) — [specs/questionnaire-design](specs/questionnaire-design/spec.md)
- [ ] Validation engine (style, grammar, QTI compliance checks; rules grounded in SURVEY_DESIGN_GUIDELINES.md)
- [ ] Auto-tagging engine (metadata suggestion)
- [ ] QTI 3.0 import/export (XML parsing and generation)
- [ ] Survey creation via adapter API: LimeSurvey + Qualtrics → direct API push (`create_survey()`); SurveyMonkey + QTI → file download fallback
- [ ] Stateless REST API endpoints (suggest, validate, tag, import, export, create) — callable independently for institutional integrations
- [ ] Stateful conversational API (session-scoped chat + draft Survey in state; LLM uses stateless tools as its toolkit)
- [ ] Document upload for survey drafting: upload slide deck / Word doc → LLM extracts structure → generates initial question draft
- [ ] FastAPI integration
- [ ] Unit tests for parsing, validation, tagging
- [ ] Integration tests: questionnaire import → suggest → export flow
- [ ] Docker container for M-Chat service
- [ ] M-Chat UI (conversational chat interface, parallel to m_ui for M-Autofill)

**Key Files:**

- `m_chat/suggestion_engine.py` (LLM-based suggestions)
- `m_chat/validation_engine.py` (Style & QTI compliance checks)
- `m_chat/tagging_engine.py` (Auto-tagging)
- `m_chat/qti_parser.py` (QTI import/export)
- `m_chat/api.py` (FastAPI endpoints)

**Dependencies:** Phase 1

**Success Criteria:**

- Suggestions generated with reasoning
- Validation catches style/grammar issues
- Tags suggested appropriately
- QTI import/export round-trips correctly (questions preserved)
- All unit & integration tests passing

---

## Phase 5: Integration & Pilot (Apr)

**Goal:** Integrate both modules, deploy to pilot sites, begin evaluation.

**Deliverables:**

- [ ] Docker Compose setup with both services (M-Chat + M-Autofill + Keycloak)
- [ ] Deployment to PXL + Belnet partner institutions
- [ ] Configure Keycloak realm for each pilot institution (optional: federate with institutional IdP via Keycloak admin panel — no code changes required; see `docs/KEYCLOAK_SETUP.md`)
- [ ] Session persistence (file-based audit reports, user downloads)
- [ ] Pilot user testing with administrators and respondents
- [ ] Collect metrics: authoring time, response time, citation accuracy, acceptance/edit rates
- [ ] Bug fixes from pilot feedback

**Note:** OIDC authentication with Keycloak is already implemented (`update-auth-oidc`, archived 2026-03-03). Keycloak is bundled in `docker-compose.yml` with a pre-configured realm; `docker-compose up` is sufficient for a working deployment including auth. Institutional SSO federation (Shibboleth, Azure AD, LDAP) is optional and operator-configured via Keycloak — no application code changes required.

**Note:** Audit reports are stored on the filesystem (per-session directory under `sessions/`). This is the intended implementation — no relational database is needed. File-based storage reinforces user isolation and simplifies deployment.

**Key Components:**

- `docker-compose.yml` (M-Chat, M-Autofill, Keycloak)
- `keycloak/realm-export.json` (pre-configured realm, auto-imported on first startup)
- Monitoring & logging setup (`logs/security.log` already in place)
- Pilot testing protocol & evaluation scripts

**Dependencies:** Phase 3, Phase 4

**Success Criteria:**

- Both services running reliably in production
- Users can authenticate via Keycloak (self-registration or institutional federation)
- Audit reports generated and downloadable per session
- Pilot metrics collected successfully
- ≥80% uptime during pilot period
- No critical security issues

---

## Phase 6: Refinement & Dissemination (May)

**Goal:** Finalize, document, and demonstrate for GÉANT TNC.

**Deliverables:**

- [ ] Bug fixes from pilot feedback
- [ ] Final evaluation report (metrics, insights, recommendations)
- [ ] Deployment documentation (Docker, environment, setup)
- [ ] Integration documentation (SDK examples, API reference)
- [ ] Admin templates & institutional reuse guides
- [ ] Live demo for GÉANT TNC (May 2026)
- [ ] Open-source release (restricted license TBD)
- [ ] Architecture & lessons-learned writeup

**Dependencies:** Phase 5

**Success Criteria:**

- All metrics compiled and analyzed
- Documentation complete and reviewed
- Live demo successful at GÉANT TNC
- Open-source release prepared

---

## Out of Scope (Post-PoC)

The following are explicitly _not_ included in the MVP/PoC:

- Audio/video transcription for documents
- Advanced re-ranking or answer filtering
- Conditional branching logic in questionnaires
- Exotic QTI question types
- Local LLM support (OpenRouter only)
- Persistent PostgreSQL database (audit reports via filesystem initially)
- Advanced analytics or reporting dashboards
- Fine-tuning or model training on user data
- Multi-language support

These are candidates for future phases based on pilot feedback.

---

## Change Proposal Sequencing

Each phase will be implemented via change proposals (stored in `openspec/changes/`):

- **Phase 1:** `setup-shared-infrastructure` (models, LLM, auth)
- **Phase 2:** `setup-document-processing` (ingestion, vector DB, chunking)
- **Phase 3:**
  - `implement-autofill-rag-citations` (RAG, citations)
  - `implement-autofill-audit-logging` (audit trail, reports, retention)
  - `implement-autofill-api-endpoints` (API, middleware, integration)
- **Phase 4:** `implement-chat-design` (suggestions, validation, tagging, QTI)
- **Phase 5:** `integrate-and-deploy` (Docker, OAuth, monitoring)
- **Phase 6:** `finalize-and-release` (docs, demo, open-source)

Each proposal will include a `proposal.md`, `tasks.md`, and spec deltas updating the capability specs as needed.

---

## Monitoring & Checkpoints

**After Phase 1:** Verify foundation layer is solid; LLM calls working, models serializing correctly.

**After Phase 2:** Full document ingestion pipeline working; semantic search accurate.

**After Phase 3:** M-Autofill functional end-to-end; citations match sources; manual testing validates quality.

**After Phase 4:** M-Chat functional; QTI round-trip successful; validation rules enforced.

**After Phase 5:** Pilot deployment successful; metrics collection in progress.

**After Phase 6:** Evaluation complete; final report and open-source release ready.

---

## References

- [Project Context](project.md) — Detailed specifications, tech stack, conventions
- [Capability Specs](specs/) — Detailed requirements for each capability
- [OpenSpec Workflow](AGENTS.md) — Process guidelines for creating change proposals
