# Project Context

## Purpose

An AI-assisted survey platform designed to improve questionnaire quality and response completeness while prioritizing privacy and user control. Two AI helpers work together:

- **M-Chat**: Assists administrators in designing better questionnaires faster (suggestions, style guidelines, evaluation rules)
- **M-Autofill**: Supports respondents with evidence-based answer suggestions drawn from their uploaded documents, with full citations and transparency

The platform operates "privacy by default" with on-premise deployment options, strict tenant isolation, and minimal data processing. Pilot runs Jan-May 2026 at PXL University College and partner institutions, with results shared at GÉANT TNC and core components released as open-source for the GÉANT community.

## Tech Stack

**Backend:**

- Python with FastAPI (async-capable framework ideal for LLM workloads)

**Frontend:**

- None (API-only architecture); response data exposed via REST API for integration into existing institutional tools and survey platforms

**AI/ML:**

- OpenRouter for LLM access with fallback to OpenAI-compatible APIs
- Support for local/self-hosted LLMs (Ollama, LM Studio, etc.) to enable privacy-first on-premise deployments

**Database:**

- PostgreSQL for relational data (surveys, responses, metadata, audit trails)
- ChromaDB (initially) for vector storage and RAG pipelines

**Standards & Compatibility:**

- QTI 3.0 (Question & Test Interoperability) for questionnaire interchange and compatibility with existing educational and institutional tools

**Deployment & Infrastructure:**

- Docker and Docker Compose for containerized, reproducible deployments
- Designed for on-premise execution with minimal external dependencies

**Authentication & Authorization:**

- OIDC (OpenID Connect) and JWT for secure API access and token-based authentication
- Keycloak as the default bundled identity provider (self-hosted, EU data locality)
- Provider-agnostic: any OIDC-compliant provider works without code changes
- Optional institutional federation (Shibboleth, Azure AD, LDAP) via Keycloak admin panel

**Testing:**

- pytest for unit and integration testing
- Acknowledge LLM-based features require specialized testing approaches (e.g., citation accuracy, response relevance); deterministic test cases for non-LLM components

## Project Conventions

We are using python inside a virtual environment (source .venv/bin/activate)
Our executables are pip3 and python3 (not pip and python)

### Code Style

- **Priority**: Simplicity, clarity, and maintainability over completeness; this is a proof of concept
- **Standard Python conventions** (hard rule): PEP 8 naming conventions (snake_case for variables/functions, PascalCase for classes)
- **Code formatting**: PyCharm default formatting style (soft rule)
- **Type hints**: Use where possible to improve code clarity and IDE support
- **Documentation**: Concise only where necessary; omit comments for self-explanatory code. Use docstrings for functions/classes that benefit from explanation

### Architecture Patterns

**Modular Organization:**

- `shape-api/`: Questionnaire design assistant (suggestion generation, QTI validation, style rule application)
- `cue-api/`: Answer suggestion assistant (document processing, RAG, citation generation)
- `m-shared/`: Common utilities (LLM client abstraction, vector DB client, data models, auth, error handling)

**M-Autofill Document Processing Pipeline:**

- File upload (PDF, DOCX, text, audio, video) → pre-process to text → chunk using configurable strategy → generate embeddings → store in ChromaDB
- Original files discarded after processing to minimize data retention
- Each document chunk stores metadata (source, position/percentage, timestamp) to enable precise citations

**RAG & Citation Strategy:**

- Semantic vector search (ChromaDB) for retrieval
- Citation system: Store chunk-to-source mappings with document metadata (line numbers, percentages, timestamps) to reconstruct evidence trails
- LLM generates answer draft + citations showing which sources informed each part of the response
- No re-ranking; use direct semantic similarity results

**Session & Tenant Isolation:**

- Single-institution deployment model (each organization hosts own instance)
- Session-based isolation: Each user session is a separate container for documents, vector stores, and temporary data
- Per-session ChromaDB instance (ephemeral SQLite database) created on upload, destroyed on session cleanup
- TTL-based data expiration: Temporary local filesystem storage cleaned up by scheduled job (configurable, ~24-48h default)
- Users can resume sessions within TTL window; remaining time exposed in API responses

**Audit & Compliance:**

- Session audit report generated on completion: captures reasoning, sources used, citations, system decisions, and timestamps
- User downloads report; if unclaimed after ~1 year, automatically deleted
- Operational data (documents, vectors, temporary files) deleted when session expires or user explicitly ends it
- Privacy/EULA endpoint provides transparency on data handling; consent captured at session start

### Testing Strategy

**Deterministic Components (Required):**

- **Document processing**: Unit tests for chunking, text extraction, metadata tagging (file-type-specific)
- **Data models & validation**: QTI schema compliance, data serialization/deserialization
- **Session management**: Creation, TTL tracking, cleanup, isolation boundaries
- **Vector DB operations**: Indexing, search, metadata filtering, per-session isolation
- **API endpoints**: Authentication, authorization, request validation, error handling
- **Tool**: pytest with fixtures for sample documents and test data

**LLM-Based Components (Future/Nice-to-Have):**

- Citation accuracy: Does the LLM cite the correct sources for each claim?
- Answer relevance: Are suggestions actually answering the question?
- Approach: LLM-based evaluation frameworks (e.g., RAGAS-style evaluation) using a second LLM to assess quality
- Timing: Post-PoC refinement phase; manual spot-checks sufficient for initial validation

**Test Data:**

- To be sourced from pilot participants and institutional survey samples
- Placeholder/synthetic data acceptable for unit tests in the interim

### Git Workflow

**Repository Structure:**

- GitHub monorepo containing `shape-api/`, `cue-api/`, and `m-shared/` modules

**Branching Strategy:**

- `main`: Production-ready code; protected branch, requires review before merge
- `develop`: Integration branch for feature development; base for feature branches
- Feature branches: `feature/`, `fix/`, `docs/` prefixes off `develop`; merge via PR after review

**Commit Messages:**

- Capitalized prefixes: `FEAT:`, `FIX:`, `CHANGE:`, `DOCS:`, `TEST:`, `REFACTOR:`, `CHORE:`
- Example: `FEAT: Add citation metadata to document chunks`

**Pull Requests:**

- Required for all merges to `main` and `develop`
- Code review: @stilkin-pxl as reviewer
- Squash and merge to `develop`; rebase and merge to `main` for clean history

**Versioning:**

- Semantic Versioning (semver): `MAJOR.MINOR.PATCH` (e.g., `0.1.0` → `0.2.0` → `0.2.1`)
- Version bumped on `main` merges; tag releases with `v` prefix (e.g., `v0.1.0`)
- During PoC phase (Jan-May 2026): Stay on `0.x.y`; `1.0.0` post-pilot evaluation

## Domain Context

**Questionnaire & Survey Concepts:**

- Core entities: Survey (questionnaire), Section (page), Question, Answer (submission/response)
- Common question types: Open-ended, Multiple Choice, Single Choice, Ranking/Ordering, Scale/Range, Slider
- Metadata & tagging: Labels, answer types, answer options, tags for organization and categorization
- Context: Not education-specific; applicable to any complex questionnaire scenarios

**QTI 3.0 Standard:**

- Internal representation: Use flexible internal data model for simplicity and speed
- Interoperability: Support QTI 3.0-compatible ingestion (import questionnaires) and export (generate QTI-compliant output via dedicated endpoint)
- Subset approach: Support most common QTI question types and structures; full QTI extensibility not required for PoC

**GDPR & Data Protection:**

- Data minimization: Minimal processing, session-based ephemeral storage, no unnecessary retention
- User rights: Provide transparent endpoints explaining data handling, consent management, and privacy safeguards
- Right to deletion: TTL-based automatic deletion of operational data; Right to Be Forgotten (RTBF) applies to audit data
- Privacy by default: All design decisions prioritize privacy; opt-in for external services, strict tenant isolation

**Privacy-First Design Principles:**

- No user profiling: Avoid behavioral analysis, fingerprinting, or algorithmic profiling
- No cross-session tracking: Sessions are isolated; no identifier correlation across sessions
- Encryption & cybersecurity: Follow OWASP Top 10 guidance; prioritize defense against injection attacks, broken authentication, sensitive data exposure, and access control flaws
- Security hardening: Secure secrets management, TLS for transit, encryption at rest where practical

## Important Constraints

- **Timeline**: Pilot phase Jan-May 2026; prototype must be production-ready for institutional deployment and GÉANT TNC demo by end of May
- **Team**: 3 part-time research/developers; AI-assisted development (code generation, debugging, documentation) expected as force multiplier
- **Budget**: OpenRouter API costs; careful cost management for token usage during pilot phase
- **Data locality**: All data processing and storage exclusive to EU during pilot; no data transfer or processing outside EU
- **Integration scope**: Design for "common questionnaire scenarios" via QTI 3.0 compatibility; avoid over-engineering for edge cases

## External Dependencies

**LLM Services:**

- **OpenRouter** (primary): LLM API gateway providing access to multiple models with cost optimization and reliability
- **OpenAI-compatible APIs**: Fallback support for OpenAI, Anthropic, or other OpenAI-compatible endpoints
- **Local LLM support**: Ollama, LM Studio, or other self-hosted models for privacy-first on-premise deployments

**Vector Database:**

- **ChromaDB**: Lightweight vector DB for semantic search and RAG; embedded SQLite backend for session-scoped isolation

**Document Processing:**

- **MarkItDown** (0.1.4): Multi-format document extraction (PDF, DOCX, images, audio transcription); note: still in beta; evaluate alternatives (Unstructured.io, pdfplumber, pytesseract) if stability issues arise

**Infrastructure & Runtime:**

- **Docker & Docker Compose**: Containerization and local orchestration
- **PostgreSQL**: Relational database (future; may be integrated at a later phase)

**Integration & Standards:**

- **QTI 3.0**: Questionnaire interchange standard; specific tools and integrations TBD during pilot based on partner institutional systems

## Future Work / Deferred

Items consciously deferred past the PoC phase. Revisit after pilot feedback.

### Conditional / Display Logic (branching)

Survey platforms (LimeSurvey, Qualtrics) support skip logic and display conditions on
questions ("show this question only if previous answer = X"). This logic is currently
discarded on import and not represented in the internal data model.

**Recommended approach when revisited:**
- Store raw platform-native logic in `question.metadata["display_logic"]` during import
  and restore it verbatim on export (opaque round-tripping — no internal model changes).
- A first-class `conditions` field on `Question` and active AI reasoning about branching
  logic in shape-api are post-PoC scope.

**Relevant for:** shape-api (questionnaire design, round-trip fidelity); not relevant for
cue-api (suggestion system does not need to execute branching logic).

### Matrix / Grid Questions

Qualtrics `Matrix` type is currently imported as `SINGLE_CHOICE` (sub-question structure
lost). LimeSurvey array types (`A`, `B`, `E`) are skipped entirely. Acceptable for the
PoC; revisit if pilot surveys rely heavily on matrix questions.
