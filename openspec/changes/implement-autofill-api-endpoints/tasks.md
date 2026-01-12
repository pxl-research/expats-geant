# Tasks: Implement M-Autofill REST API & FastAPI Integration

## 1. API Design & Schema Definition

- [ ] 1.1 Define API request/response schemas

  - [ ] 1.1a POST /upload — Upload documents (multipart/form-data)
    - Request: file, session_id (implicit from JWT)
    - Response: { status: "success", filename, size_bytes, upload_timestamp }
  - [ ] 1.1b POST /suggest — Request answer suggestion
    - Request: { question, context (optional), session_id (implicit) }
    - Response: { answer, citations: [{source, position, timestamp, excerpt}], metadata }
  - [ ] 1.1c GET /audit-report — Retrieve audit report (session_id from JWT)
    - Request: Optional time_range, format (json/plaintext)
    - Response: audit report (structured or formatted)
  - [ ] 1.1d DELETE /session — Cleanup session explicitly
    - Request: session_id (implicit from JWT)
    - Response: { status: "success", deleted_timestamp }
  - [ ] 1.1e GET /privacy — Privacy/consent disclosure
    - Request: (none)
    - Response: plaintext privacy statement
  - [ ] 1.1f GET /session — Session status (optional; check remaining TTL)
    - Request: (implicit from JWT)
    - Response: { session_id, created_at, expires_at, remaining_time_seconds, documents_count }

- [ ] 1.2 Document API in OpenAPI/Swagger format
  - [ ] 1.2a Generate OpenAPI spec from FastAPI annotations
  - [ ] 1.2b Test Swagger UI at /docs endpoint

## 2. FastAPI Application Setup

- [ ] 2.1 Create `m_autofill/api.py`

  - [ ] 2.1a Initialize FastAPI app with title, description, version
  - [ ] 2.1b Configure CORS (if needed for frontend integration)
  - [ ] 2.1c Configure request validation (FastAPI's built-in pydantic)
  - [ ] 2.1d Add global error handler for ValidationError, FileUploadError, etc.

- [ ] 2.2 Implement error handling & status codes
  - [ ] 2.2a Define error response schema (error_code, message, timestamp)
  - [ ] 2.2b Handle 400 (validation error), 401 (auth), 404 (not found), 500 (internal)
  - [ ] 2.2c Ensure all errors logged to audit trail

## 3. Endpoint Implementation

- [ ] 3.1 POST /upload endpoint

  - [ ] 3.1a Accept multipart file upload (PDF, DOCX, TXT, MD)
  - [ ] 3.1b Validate file (size, type, via m_autofill/validation.py)
  - [ ] 3.1c Call m_autofill/ingest.py to process document
  - [ ] 3.1d Log upload to audit trail (via 3.2 audit logger)
  - [ ] 3.1e Return success response with filename and timestamp

- [ ] 3.2 POST /suggest endpoint

  - [ ] 3.2a Validate question (non-empty, length, no injection)
  - [ ] 3.2b Call m_autofill/rag_pipeline.py to generate suggestion
  - [ ] 3.2c Call audit logger to log suggestion generation
  - [ ] 3.2d Return answer + citations
  - [ ] 3.2e Handle edge cases (no documents uploaded, no results, LLM error)

- [ ] 3.3 GET /audit-report endpoint

  - [ ] 3.3a Call audit logger to generate report (from 3.2)
  - [ ] 3.3b Support format option (json, plaintext)
  - [ ] 3.3c Mark report as claimed if user downloads
  - [ ] 3.3d Return report content (download or view)

- [ ] 3.4 DELETE /session endpoint

  - [ ] 3.4a Call session manager to cleanup session (from Phase 2)
  - [ ] 3.4b Log session termination to audit trail
  - [ ] 3.4c Delete documents, vectors, temporary files
  - [ ] 3.4d Preserve audit report (for user retention window)
  - [ ] 3.4e Return success response

- [ ] 3.5 GET /privacy endpoint

  - [ ] 3.5a Return plaintext privacy/GDPR statement
  - [ ] 3.5b Include data handling, retention, user rights
  - [ ] 3.5c Include consent terms (what user agreed to at session start)

- [ ] 3.6 GET /session endpoint (optional; helpful for clients)
  - [ ] 3.6a Return session metadata: session_id, created_at, expires_at, remaining_time
  - [ ] 3.6b Return document count (how many uploaded)
  - [ ] 3.6c Help clients track session TTL

## 4. Session/Auth Middleware Integration

- [ ] 4.1 Integrate session middleware

  - [ ] 4.1a Middleware extracts JWT from Authorization header
  - [ ] 4.1b Middleware validates JWT (existing auth/jwt_handler.py)
  - [ ] 4.1c Middleware creates or retrieves session (from Phase 2 SessionManager)
  - [ ] 4.1d Middleware injects session_id into request context

- [ ] 4.2 Implicit session creation

  - [ ] 4.2a First authenticated request automatically creates session
  - [ ] 4.2b Session TTL set from config (default: 24–48 hours)
  - [ ] 4.2c Subsequent requests reuse existing session (from JWT)
  - [ ] 4.2d Session cleanup on DELETE /session or TTL expiration

- [ ] 4.3 Test middleware
  - [ ] 4.3a Verify session creation on first request
  - [ ] 4.3b Verify session isolation (different JWT → different session)
  - [ ] 4.3c Verify expired session handling (rejected or recreated)

## 5. Integration Tests

- [ ] 5.1 Full user session flow tests

  - [ ] 5.1a Initialize session (implicit on first request)
  - [ ] 5.1b Upload document
  - [ ] 5.1c Request suggestion
  - [ ] 5.1d Verify suggestion + citations
  - [ ] 5.1e Request audit report
  - [ ] 5.1f Verify audit report completeness
  - [ ] 5.1g Cleanup session

- [ ] 5.2 Multi-document flow

  - [ ] 5.2a Upload multiple documents
  - [ ] 5.2b Request multiple suggestions
  - [ ] 5.2c Verify all sources correctly cited
  - [ ] 5.2d Verify audit report lists all documents and suggestions

- [ ] 5.3 Session isolation tests

  - [ ] 5.3a User A uploads docs, requests suggestion
  - [ ] 5.3b User B (different JWT) uploads different docs
  - [ ] 5.3c Verify User A cannot see User B's documents
  - [ ] 5.3d Verify suggestions use correct documents per user

- [ ] 5.4 Error handling tests

  - [ ] 5.4a Invalid file upload (wrong type, oversized)
  - [ ] 5.4b Missing authorization (no JWT)
  - [ ] 5.4c Malformed request (invalid JSON)
  - [ ] 5.4d Suggestion with no documents uploaded
  - [ ] 5.4e Session not found (expired or invalid)

- [ ] 5.5 Endpoint contract tests
  - [ ] 5.5a Test response schemas (all fields present, correct types)
  - [ ] 5.5b Test status codes (200, 400, 401, 404, 500)
  - [ ] 5.5c Test error response format

## 6. Manual Testing & QA

- [ ] 6.1 End-to-end testing via HTTP client (curl, Postman, client library)

  - [ ] 6.1a Test happy path (upload → suggest → audit → cleanup)
  - [ ] 6.1b Test with real documents (multi-page PDFs, varied content)
  - [ ] 6.1c Verify suggestion quality and citation accuracy (manual review)

- [ ] 6.2 Performance & stress testing

  - [ ] 6.2a Test upload with large file (40–50 MB, near limit)
  - [ ] 6.2b Test suggestion response time (target: <5 seconds)
  - [ ] 6.2c Test concurrent sessions (multiple users simultaneously)

- [ ] 6.3 Security testing
  - [ ] 6.3a Test JWT validation (invalid/expired tokens)
  - [ ] 6.3b Test request validation (injection attempts, oversized payloads)
  - [ ] 6.3c Test session isolation (cross-session data access attempts)

## 7. Docker & Deployment

- [ ] 7.1 Create Dockerfile for M-Autofill

  - [ ] 7.1a Base image: python:3.11-slim
  - [ ] 7.1b Install dependencies (requirements.txt)
  - [ ] 7.1c Copy application code
  - [ ] 7.1d Expose port 8001 (or configured port)
  - [ ] 7.1e CMD: uvicorn m_autofill.api:app --host 0.0.0.0 --port 8001

- [ ] 7.2 Create/update docker-compose.yml

  - [ ] 7.2a Define m_autofill service (image, port, environment)
  - [ ] 7.2b Set environment variables (LLM_API_KEY, CHROMA_PATH, etc.)
  - [ ] 7.2c Add healthcheck (GET /docs or simple endpoint)
  - [ ] 7.2d Link to PostgreSQL or other services (if needed)

- [ ] 7.3 Test Docker build and run

  - [ ] 7.3a Build image: docker build -t m-autofill:latest .
  - [ ] 7.3b Run container: docker run -p 8001:8001 m-autofill:latest
  - [ ] 7.3c Verify API accessible at localhost:8001
  - [ ] 7.3d Test endpoints via HTTP requests

- [ ] 7.4 Docker Compose orchestration
  - [ ] 7.4a Run full stack: docker-compose up
  - [ ] 7.4b Verify all services healthy
  - [ ] 7.4c Test inter-service communication (m_autofill ↔ chroma, etc.)

## 8. Documentation

- [ ] 8.1 API documentation

  - [ ] 8.1a OpenAPI/Swagger spec (auto-generated by FastAPI)
  - [ ] 8.1b Example curl commands for each endpoint
  - [ ] 8.1c Response examples (success and error cases)

- [ ] 8.2 Deployment documentation

  - [ ] 8.2a Docker build and run instructions
  - [ ] 8.2b Environment variables (LLM_API_KEY, CHROMA_PATH, etc.)
  - [ ] 8.2c Health check and monitoring

- [ ] 8.3 Code comments & docstrings
  - [ ] 8.3a Docstrings for all endpoint functions
  - [ ] 8.3b Comments for middleware and error handling

## Definition of Done

- ✅ All implementation tasks complete
- ✅ All integration tests passing (minimum: 20+ tests)
- ✅ Manual end-to-end testing successful
- ✅ Docker build and run verified
- ✅ OpenAPI documentation complete and accurate
- ✅ No critical security issues found
- ✅ Ready for Phase 5 integration
