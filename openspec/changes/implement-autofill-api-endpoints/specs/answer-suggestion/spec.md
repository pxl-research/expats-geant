# API Specification: M-Autofill REST Endpoints

## Endpoints Overview

### Core Endpoints

1. **POST /upload** – Upload documents to session
2. **POST /suggest** – Request answer suggestion
3. **GET /audit-report** – Retrieve session audit report
4. **DELETE /session** – Cleanup session explicitly
5. **GET /privacy** – Privacy/GDPR disclosure
6. **GET /session** – Session status (optional)

---

## POST /upload

**Summary:** Upload a document to the session for use in answer suggestions.

**Authentication:** Required (JWT token in Authorization header)

**Request:**

```
Content-Type: multipart/form-data

file: (binary) — PDF, DOCX, TXT, or Markdown file
```

**Response (200 OK):**

```json
{
  "status": "success",
  "filename": "survey_guide.pdf",
  "size_bytes": 245680,
  "upload_timestamp": "2026-01-15T10:30:45Z",
  "session_id": "sess_abc123"
}
```

**Error Responses:**

- 400 Bad Request: Invalid file type, oversized, or missing
- 401 Unauthorized: Invalid or missing JWT
- 404 Not Found: Session not found (expired?)
- 500 Internal Server Error: Processing failure

---

## POST /suggest

**Summary:** Request an answer suggestion based on uploaded documents.

**Authentication:** Required (JWT token in Authorization header)

**Request:**

```json
{
  "question": "What are the eligibility criteria?",
  "context": "I'm a first-time respondent"
}
```

**Response (200 OK):**

```json
{
  "answer": "Based on your documents, first-time respondents must meet...",
  "citations": [
    {
      "source": "survey_guide.pdf",
      "position": "45%",
      "position_range": { "start_percentage": 44, "end_percentage": 46 },
      "timestamp": "2026-01-15T10:30:45Z",
      "excerpt": "first-time respondents must meet the following..."
    }
  ],
  "metadata": {
    "model_used": "openrouter/meta-llama/llama-2-70b",
    "generation_timestamp": "2026-01-15T10:35:10Z",
    "sources_count": 1
  }
}
```

**Error Responses:**

- 400 Bad Request: Invalid question format (empty, too long, injection detected)
- 401 Unauthorized: Invalid or missing JWT
- 404 Not Found: Session not found or no documents uploaded
- 500 Internal Server Error: LLM error or retrieval failure

---

## GET /audit-report

**Summary:** Retrieve the complete audit report for the session.

**Authentication:** Required (JWT token in Authorization header)

**Query Parameters:**

- `format` (optional): `json` or `plaintext` (default: `json`)
- `time_range` (optional): ISO 8601 date range (e.g., `2026-01-15T00:00:00Z,2026-01-16T00:00:00Z`)

**Response (200 OK - JSON format):**

```json
{
  "session_id": "sess_abc123",
  "created_at": "2026-01-15T10:00:00Z",
  "ended_at": "2026-01-15T11:30:00Z",
  "retention_until": "2027-01-15T11:30:00Z",
  "is_claimed": true,
  "claimed_at": "2026-01-15T11:35:00Z",
  "documents": [
    {
      "filename": "survey_guide.pdf",
      "size_bytes": 245680,
      "upload_timestamp": "2026-01-15T10:30:45Z"
    }
  ],
  "suggestions": [
    {
      "question_id": null,
      "question": "What are the eligibility criteria?",
      "suggested_answer": "Based on your documents...",
      "sources": ["survey_guide.pdf"],
      "generation_timestamp": "2026-01-15T10:35:10Z",
      "user_edited_answer": null,
      "edit_timestamp": null
    }
  ],
  "summary": {
    "total_documents": 1,
    "total_suggestions": 1,
    "total_user_edits": 0,
    "avg_sources_per_suggestion": 1.0
  }
}
```

**Response (200 OK - Plaintext format):**

```
AUDIT REPORT — Session sess_abc123
Created: 2026-01-15 10:00:00 UTC
Ended: 2026-01-15 11:30:00 UTC

DOCUMENTS UPLOADED (1):
- survey_guide.pdf (245,680 bytes) — uploaded 2026-01-15 10:30:45 UTC

SUGGESTIONS GENERATED (1):
[1] Question: What are the eligibility criteria?
    Suggestion: Based on your documents...
    Sources: survey_guide.pdf
    Generated: 2026-01-15 10:35:10 UTC
    User Edit: None

SUMMARY:
- Total Documents: 1
- Total Suggestions: 1
- Total Edits: 0
- Avg Sources per Suggestion: 1.0
```

**Error Responses:**

- 401 Unauthorized: Invalid or missing JWT
- 404 Not Found: Session not found or report not available (expired?)
- 500 Internal Server Error: Report generation failure

---

## DELETE /session

**Summary:** Explicitly cleanup the session and all associated data.

**Authentication:** Required (JWT token in Authorization header)

**Request:** (no body)

**Response (200 OK):**

```json
{
  "status": "success",
  "session_id": "sess_abc123",
  "deleted_at": "2026-01-15T11:35:00Z",
  "message": "Session cleanup complete. Audit report available until 2027-01-15."
}
```

**Side Effects:**

- All uploaded documents deleted
- All vector embeddings deleted
- Temporary files deleted
- Audit report generated and preserved for retention window
- Session marked as ended

**Error Responses:**

- 401 Unauthorized: Invalid or missing JWT
- 404 Not Found: Session not found
- 500 Internal Server Error: Cleanup failure

---

## GET /privacy

**Summary:** Retrieve privacy policy and data handling disclosure.

**Authentication:** Not required (public endpoint)

**Response (200 OK):**

```
PRIVACY POLICY & DATA HANDLING

DATA COLLECTED:
- Documents uploaded by you (processed into text chunks)
- Questions you ask
- Suggestions generated by the system
- Your edits to suggestions
- Timestamps and session metadata

DATA RETENTION:
- Session-scoped storage: Deleted when session expires (~24–48 hours)
- Audit reports: Retained for ~1 year after session end, or until you download
- Downloaded reports: Retained indefinitely (you have a copy)

DATA PROTECTION:
- Session isolation: Your documents are only visible within your session
- Encryption: Data in transit (TLS); encryption at rest where practical
- No external processing: All data processing within this instance (no cloud APIs except LLM)
- No profiling: No behavioral tracking or algorithmic profiling

YOUR RIGHTS:
- Download: You can download your audit report anytime during retention window
- Delete: You can request deletion of your audit report (Right to Be Forgotten)
- Access: You can review all data collected via the audit report
- Transparency: This policy is always accessible

CONSENT:
By using this service, you consent to:
- Data collection and logging as described above
- Audit report generation and retention for ~1 year
- Automatic deletion of expired reports and session data

For questions or to exercise your rights, contact: [contact information]
```

**Error Responses:**

- 500 Internal Server Error: Policy retrieval failure (unlikely)

---

## GET /session

**Summary:** Retrieve current session metadata and status.

**Authentication:** Required (JWT token in Authorization header)

**Response (200 OK):**

```json
{
  "session_id": "sess_abc123",
  "created_at": "2026-01-15T10:00:00Z",
  "expires_at": "2026-01-16T10:00:00Z",
  "remaining_time_seconds": 82000,
  "documents_count": 1,
  "is_active": true,
  "status": "ready"
}
```

**Error Responses:**

- 401 Unauthorized: Invalid or missing JWT
- 404 Not Found: Session not found (expired)

---

## Error Response Format

All error responses follow this schema:

```json
{
  "error_code": "VALIDATION_ERROR",
  "message": "Question is required and must be non-empty",
  "timestamp": "2026-01-15T10:35:10Z",
  "request_id": "req_xyz789"
}
```

**Common Error Codes:**

- `VALIDATION_ERROR` – Request validation failed (400)
- `UNAUTHORIZED` – Missing or invalid authentication (401)
- `SESSION_NOT_FOUND` – Session expired or invalid (404)
- `FILE_UPLOAD_ERROR` – File validation or processing failed (400)
- `LLM_ERROR` – Answer generation failed (500)
- `INTERNAL_ERROR` – Unexpected server error (500)
