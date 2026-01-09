# Development Plan

This document outlines the phased approach to building Expat-GÉANT from January to June 2026, aligned with the baseline capability specs in `specs/`.

## Project Timeline

- **Start:** January 2026
- **Pilot & Evaluation:** January–May 2026 (PXL + Belnet partners)
- **Demo & Dissemination:** June 2026 (GÉANT TNC)
- **Final Report:** 31 July 2026

## Phase 1: Foundation & Shared Infrastructure (Jan–Feb)

**Goal:** Establish core building blocks for both M-Chat and M-Autofill.

**Deliverables:**

- ✅ [Baseline capability specs](specs/) defined
- ✅ Data models (Survey, Section, Question, Response, Citation, Session) — [specs/data-models](specs/data-models/spec.md)
- ✅ LLM client (OpenRouter integration) — [specs/llm-integration](specs/llm-integration/spec.md)
- [ ] Basic auth (JWT token generation & validation) — [specs/auth-security](specs/auth-security/spec.md)
- ✅ Unit tests for models and LLM client
- ⏳ Development environment setup (Docker, requirements.txt, .env example)

**Key Files:**

- ✅ `m_shared/models/*.py` (Survey, Section, Question, AnswerOption, Response, Citation, Session)
- [ ] `m_shared/llm/client.py` (OpenRouter client with retries)
- [ ] `m_shared/auth/jwt_handler.py` (Token creation/validation)

**Dependencies:** None (foundation layer)

**Success Criteria:**

- ✅ Models serialize/deserialize correctly with validation
- [ ] LLM client successfully calls OpenRouter
- [ ] JWT tokens can be created and validated
- [ ] All unit tests passing

---

## Phase 2: Document Processing & Vector Search (Feb–Mar)

**Goal:** Enable document upload, chunking, and semantic search for M-Autofill.

**Deliverables:**

- [ ] Document ingestion pipeline (text extraction, chunking) — [specs/document-ingestion](specs/document-ingestion/spec.md)
- [ ] Vector DB client (ChromaDB wrapper with session isolation) — [specs/vector-db](specs/vector-db/spec.md)
- [ ] Session management & TTL cleanup
- [ ] Input validation & sanitization (auth-security) — [specs/auth-security](specs/auth-security/spec.md)
- [ ] Unit tests for chunking, embedding, search
- [ ] Integration test: upload → chunk → search flow

**Key Files:**

- `m_autofill/document_processor.py` (Upload, parse, chunk)
- `m_shared/vectordb/client.py` (ChromaDB wrapper, session isolation)
- `m_shared/utils/validators.py` (Input validation)

**Dependencies:** Phase 1 (data models, LLM client)

**Success Criteria:**

- Documents uploaded, parsed, and chunked correctly
- Semantic search returns relevant chunks
- Session isolation working (no cross-session data leakage)
- TTL cleanup removes expired sessions
- All unit & integration tests passing

---

## Phase 3: M-Autofill (Answer Suggestion Module) (Mar–Apr)

**Goal:** Complete RAG pipeline with answer suggestions, citations, and audit logging.

**Deliverables:**

- [ ] RAG pipeline (retrieval + LLM generation) — [specs/answer-suggestion](specs/answer-suggestion/spec.md)
- [ ] Citation system (track sources, metadata, highlights)
- [ ] Session audit trail & report generation — [specs/audit-compliance](specs/audit-compliance/spec.md)
- [ ] REST API endpoints (upload, suggest, audit, cleanup)
- [ ] FastAPI integration with session/auth middleware
- [ ] Manual testing of suggestion quality & citation accuracy
- [ ] Integration tests: full user session flow
- [ ] Docker container for M-Autofill service

**Key Files:**

- `m_autofill/rag_pipeline.py` (Retrieval, generation, citations)
- `m_autofill/api.py` (FastAPI endpoints)
- `m_shared/utils/audit.py` or `m_autofill/audit.py` (Audit logging)

**Dependencies:** Phase 1, Phase 2

**Success Criteria:**

- Suggestions generated with cited sources
- Citations include source metadata (filename, position, timestamp)
- Audit trail captures all session activity
- API endpoints respond correctly
- Manual review: citation accuracy ≥ 90%
- All unit, integration, and manual tests passing

---

## Phase 4: M-Chat (Questionnaire Design Module) (Apr–May)

**Goal:** Complete questionnaire design assistant with validation, suggestions, tagging, and QTI support.

**Deliverables:**

- [ ] Question suggestion engine (LLM-based rewording) — [specs/questionnaire-design](specs/questionnaire-design/spec.md)
- [ ] Validation engine (style, grammar, QTI compliance checks)
- [ ] Auto-tagging engine (metadata suggestion)
- [ ] QTI 3.0 import/export (XML parsing and generation)
- [ ] REST API endpoints (suggest, validate, tag, import, export)
- [ ] FastAPI integration
- [ ] Unit tests for parsing, validation, tagging
- [ ] Integration tests: questionnaire import → suggest → export flow
- [ ] Docker container for M-Chat service

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

## Phase 5: Integration & Pilot (May)

**Goal:** Integrate both modules, deploy to pilot sites, begin evaluation.

**Deliverables:**

- [ ] Docker Compose setup with both services
- [ ] OAuth 2.0 integration for institutional SSO (spec: auth-security)
- [ ] Session persistence (audit reports, user downloads)
- [ ] Deployment to PXL + Belnet partner institutions
- [ ] Pilot user testing with administrators and respondents
- [ ] Collect metrics: authoring time, response time, citation accuracy, acceptance/edit rates
- [ ] Bug fixes from pilot feedback

**Key Components:**

- `docker-compose.yml` (M-Chat, M-Autofill, PostgreSQL for audit reports)
- OAuth provider configuration (institutional Shibboleth/Azure AD)
- Monitoring & logging setup
- Pilot testing protocol & evaluation scripts

**Dependencies:** Phase 3, Phase 4

**Success Criteria:**

- Both services running reliably in production
- Users can authenticate via institutional SSO
- Pilot metrics collected successfully
- ≥80% uptime during pilot period
- No critical security issues

---

## Phase 6: Refinement & Dissemination (Jun)

**Goal:** Finalize, document, and demonstrate for GÉANT TNC.

**Deliverables:**

- [ ] Bug fixes from pilot feedback
- [ ] Final evaluation report (metrics, insights, recommendations)
- [ ] Deployment documentation (Docker, environment, setup)
- [ ] Integration documentation (SDK examples, API reference)
- [ ] Admin templates & institutional reuse guides
- [ ] Live demo for GÉANT TNC (June 2026)
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
- **Phase 3:** `implement-autofill-rag` (RAG, citations, audit)
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
