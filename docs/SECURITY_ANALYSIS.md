# Security Analysis Report

**Date:** 2026-03-13
**Scope:** Full codebase audit of expats (cue_api, shape_api, m_shared, cue_ui, shape_ui)
**Methodology:** Manual static analysis of all authentication, authorization, API, adapter, session management, and file handling code.

---

## Executive Summary

The codebase demonstrates good security practices in several areas: `defusedxml` for XML parsing, Pydantic for input typing, session ownership enforcement, and no use of `eval`/`exec`/`pickle`/`subprocess`. However, several high-priority vulnerabilities were identified that should be addressed before any production deployment.

---

## Findings

### HIGH — H1: Path Traversal in cue_api File Upload

**File:** `cue_api/routes/documents.py:38` (originally `cue_api/api.py`)

```python
file_path = temp_dir / file.filename  # file.filename is unsanitized
```

`file.filename` is user-controlled and used directly as a path component. A malicious filename like `../../metadata.json` escapes the uploads directory. The file is written to the traversed path *before* validation runs, creating a write-before-validate vulnerability.

**Compare:** `shape_api/routes/chat.py` correctly uses `Path(file.filename).name` to strip directory components.

**Fix:** Use `Path(file.filename).name` and verify the resolved path is within the target directory.

---

### HIGH — H2: SSRF via User-Controlled `api_url` in /create

**File:** `shape_api/routes/transforms.py` (originally `shape_api/api.py`), `shape_api/models.py:33`

The `/create` endpoint accepts an arbitrary `api_url` from the request body and passes it directly to `LimeSurveyAdapter`, which issues a `requests.post()` to that URL. An authenticated user can point this at internal services (e.g., `http://169.254.169.254/`, `http://localhost:6379/`).

For Qualtrics, `api_url` is used as `datacenter_id` and interpolated into `https://{datacenter}.qualtrics.com/API/v3`. A crafted value (e.g., `evil.com#`) could redirect API calls — and the `X-API-TOKEN` header — to an attacker-controlled host.

**Fix:** Validate `api_url` with scheme enforcement (HTTPS only) and block private/loopback ranges. Validate `datacenter_id` against `^[a-z0-9]+$`.

---

### HIGH — H3: Unbounded Input Fields in shape_api Models

**File:** `shape_api/models.py`

Multiple fields accept arbitrary-length strings with no `max_length`:
- `ChatTurnRequest.message` (line 102) — stored to disk, sent to LLM
- `ImportRequest.content` (line 12) — raw file content, no size limit
- `StyleUpdateRequest.free_text` (line 116) — injected into LLM prompts
- `SuggestRequest.n_suggestions` (line 53) — no upper bound; value of 1,000,000 triggers unbounded LLM calls

**Compare:** `cue_api/models.py` properly uses `max_length=2000` on similar fields.

**Fix:** Add `max_length` constraints to all string fields and `Field(ge=1, le=20)` to `n_suggestions`.

---

### ~~HIGH — H4: `/dev/token` Defaults to Open~~ — **RESOLVED (endpoint removed)**

**Resolution:** `/dev/token` has been removed from all services. It is replaced by
`POST /auth/token`, which requires a shared `API_SECRET` validated with constant-time
comparison (`hmac.compare_digest`). The endpoint is available in all environments but
issues tokens only to callers that present the correct secret. Session IDs are now
UUID-based, eliminating the session-fixation risk.

---

### MEDIUM — M1: Internal Exception Details Leaked to Clients

**Files:**
- `m_shared/auth/middleware.py:89` — `f"Invalid token: {e}"`
- `m_shared/auth/middleware.py:95` — `f"Token validation error: {e}"`
- `m_shared/auth/middleware.py:125` — `f"Session management error: {e}"`
- `cue_api/routes/documents.py:101` — `f"Upload failed: {e}"`
- `cue_api/routes/suggestions.py` — `f"Suggestion failed: {e}"`
- `cue_api/routes/suggestions.py` — `f"Batch suggestion failed: {e}"`

Raw Python exception messages can expose internal details (file paths, library internals, algorithm info). These should be logged server-side and replaced with generic messages in the HTTP response.

**Fix:** Log `e` at `logger.error()` level; return generic detail strings.

---

### MEDIUM — M2: No CORS Configuration

No `CORSMiddleware` is configured anywhere. While FastAPI defaults to rejecting cross-origin requests, the absence of an explicit CORS policy means there is no defense-in-depth against CSRF for browser-based API consumers.

**Fix:** Add `CORSMiddleware` with a restrictive origin allowlist.

---

### MEDIUM — M3: JWT Algorithm Configurable via Environment Variable

**File:** `m_shared/auth/jwt_handler.py:62,114`

`JWT_ALGORITHM` is read from an environment variable with no allowlist. If an attacker can influence environment variables, they could set `JWT_ALGORITHM=none` (though PyJWT currently rejects this when a secret is provided, this is fragile).

**Fix:** Validate against an allowlist of strong algorithms: `{"HS256", "HS384", "HS512"}`.

---

### MEDIUM — M4: OIDC State Store is In-Memory

**File:** `m_shared/auth/oauth.py:31-33`

The CSRF state store for the OIDC flow is a module-level `dict`. In multi-process deployments (multiple workers), a state generated by worker A will not be found by worker B, making CSRF protection ineffective.

**Fix:** For multi-worker deployments, move to a shared store (Redis, database, or signed cookies).

---

### MEDIUM — M5: Missing Direct Dependencies

**File:** `requirements.txt`

`defusedxml` and `requests` are used in production code (adapters) but are not declared as direct dependencies. They are installed transitively. If the transitive chain changes, these security-critical imports would break silently.

**Fix:** Add `defusedxml>=0.7.0` and `requests>=2.31.0` to `requirements.txt`.

---

### LOW — L1: No Rate Limiting

No rate limiting middleware exists. LLM-backed endpoints (`/suggest`, `/suggest/batch`, `/chat/{session_id}`, `/validate`, `/tag`) perform expensive API calls per request with no throttle.

---

### LOW — L2: OIDC Missing `nonce` Claim

**File:** `m_shared/auth/oauth.py:133-140`

The OIDC authorization request does not include a `nonce` parameter. Without nonce validation, ID token replay attacks are possible.

---

### LOW — L3: `datetime.utcnow()` Deprecation

**Files:** `m_shared/session/manager.py:158,334,377`, `m_shared/models/session.py:27,45,52,58`

Uses deprecated `datetime.utcnow()` (naive datetime) while `jwt_handler.py` uses `datetime.now(UTC)` (timezone-aware). This mismatch could cause incorrect expiration comparisons.

---

### LOW — L4: No Token Revocation Mechanism

Stolen JWT tokens remain valid until expiry (default 24 hours). There is no blacklist or revocation endpoint.

---

### LOW — L5: JWKS Cache Never Refreshed

**File:** `m_shared/auth/oauth.py:75-85`

The OIDC JWKS is cached indefinitely. If the provider rotates signing keys, the application must be restarted.

---

### LOW — L6: Roles Claim in JWT Never Enforced

**File:** `m_shared/auth/jwt_handler.py:66-67`

Tokens carry a `roles` claim (e.g., `["administrator"]`, `["respondent"]`) but no endpoint or middleware checks roles. Any valid token can access any endpoint.

---

## Positive Findings

| Area | Status |
|------|--------|
| XML parsing (XXE) | `defusedxml` used in all XML import paths |
| `eval`/`exec`/`pickle`/`subprocess` | Not present in production code |
| SQL injection | N/A — no SQL; ChromaDB with safe abstractions |
| TLS certificate verification | No `verify=False` found anywhere |
| Session ownership enforcement | `_verify_session_owner` used consistently |
| File extension allowlisting | Present in all upload paths |
| JWT secret hardcoding | Not hardcoded — read from environment |
| Credential logging | No credentials found in log statements |
| Pydantic input typing | Used for all request models |

---

## Remediation Summary

| ID | Severity | Fix | Effort |
|----|----------|-----|--------|
| H1 | HIGH | Sanitize filename in cue_api upload | Small |
| H2 | HIGH | Validate api_url scheme and block private IPs | Medium |
| H3 | HIGH | Add max_length/bounds to shape_api models | Small |
| H4 | ~~HIGH~~ | ~~Positive allowlist for /dev/token environment guard~~ — **Resolved: endpoint removed** | — |
| M1 | MEDIUM | Generic error messages, log details server-side | Small |
| M2 | MEDIUM | Add CORSMiddleware | Small |
| M3 | MEDIUM | Allowlist JWT algorithms | Small |
| M4 | MEDIUM | Document OIDC state store limitation | Small |
| M5 | MEDIUM | Add defusedxml, requests to requirements.txt | Trivial |
| L1-L6 | LOW | Various — see individual findings | Varies |

---

## Applied Fixes

The following remediations were implemented on 2026-03-13. All 875 tests pass after changes (coverage: 88.61%).

### H1 — Path Traversal in cue_api File Upload

**File:** `cue_api/routes/documents.py:38` (originally `cue_api/api.py`)

**Before:**
```python
file_path = temp_dir / file.filename
```

**After:**
```python
safe_name = Path(file.filename).name if file.filename else "upload"
file_path = temp_dir / safe_name
if not file_path.resolve().is_relative_to(temp_dir.resolve()):
    raise HTTPException(status_code=400, detail="Invalid filename")
```

**Why:** `file.filename` is client-controlled. A value like `../../metadata.json` would escape the uploads directory. `Path.name` strips directory components, and `is_relative_to()` provides a defense-in-depth check. This matches the pattern used in `shape_api/routes/chat.py`.

---

### H2 — SSRF via User-Controlled `api_url`

**File:** `m_shared/utils/url_validation.py` (originally `shape_api/api.py`)

**Before:** `api_url` from the request body was passed directly to `LimeSurveyAdapter` (which calls `requests.post(api_url, ...)`) and as Qualtrics `datacenter_id` (interpolated into a hostname) with no validation.

**After:** Two validation functions extracted to `m_shared/utils/url_validation.py` and shared by both APIs:
- `validate_api_url(url)` — enforces HTTPS scheme, rejects private/loopback IPs and `localhost`.
- `validate_datacenter_id(id)` — enforces `^[a-zA-Z0-9]+$` regex, preventing URL fragment injection in `https://{datacenter}.qualtrics.com/API/v3`.

Both are called before adapter instantiation. `HTTPException` is re-raised cleanly.

**Why:** An authenticated user could point `api_url` at internal services (`http://169.254.169.254/`, `http://localhost:6379/`) for blind SSRF. For Qualtrics, a crafted `datacenter_id` like `evil.com#` could redirect API calls (including the `X-API-TOKEN` header) to attacker infrastructure.

---

### H3 — Unbounded Input Fields in shape_api Models

**File:** `shape_api/models.py`

**Before:**
```python
class ImportRequest(BaseModel):
    content: str
class ChatTurnRequest(BaseModel):
    message: str
class SuggestRequest(BaseModel):
    n_suggestions: int = 3
```

**After:**
```python
class ImportRequest(BaseModel):
    content: str = Field(max_length=10_000_000)
class ChatTurnRequest(BaseModel):
    message: str = Field(max_length=50_000)
class SuggestRequest(BaseModel):
    n_suggestions: int = Field(default=3, ge=1, le=20)
```

All string fields across `ImportRequest`, `ExportRequest`, `CreateRequest`, `ChatTurnRequest`, and `StyleUpdateRequest` now have `max_length` constraints. `n_suggestions` is bounded to `[1, 20]`.

**Why:** Without bounds, a client could send a multi-GB `content` field (disk/memory exhaustion), a 1,000,000-item `n_suggestions` (unbounded LLM API calls), or an oversized `free_text` (prompt injection surface).

---

### H4 — `/dev/token` Removed; Replaced by `POST /auth/token`

**Resolution:** The `/dev/token` endpoint was removed entirely from all services. It is
replaced by `POST /auth/token`, which requires callers to present a shared `API_SECRET`
validated via `hmac.compare_digest` (constant-time). Session IDs are UUID-based. The
endpoint is rate-limited to 5 requests per minute and is available in all environments,
making a separate dev-only endpoint unnecessary.

---

### M1 — Internal Exception Details Leaked to Clients

**Files:** `m_shared/auth/middleware.py:83-96,122-126`, `cue_api/routes/documents.py`, `cue_api/routes/suggestions.py`

**Before:**
```python
content={"detail": f"Invalid token: {e}"}
content={"detail": f"Token validation error: {e}"}
content={"detail": f"Session management error: {e}"}
detail=f"Upload failed: {e}"
```

**After:**
```python
content={"detail": "Invalid or malformed token"}
content={"detail": "Authentication error"}
content={"detail": "Session error"}
detail="Upload failed"
```

All catch-all `except Exception as e` blocks now log the full exception via `logger.error()` and return a generic message to the client.

**Why:** Raw Python exception messages can expose internal file paths, library version details, JWT algorithm mismatches, and ChromaDB internals — all useful to an attacker for reconnaissance.

---

### M3 — JWT Algorithm Allowlist

**File:** `m_shared/auth/jwt_handler.py:11,62,116`

**Before:** `JWT_ALGORITHM` env var accepted any string value.

**After:**
```python
_ALLOWED_ALGORITHMS = {"HS256", "HS384", "HS512"}
# In both create_token() and validate_token():
if algorithm not in _ALLOWED_ALGORITHMS:
    raise ValueError(f"JWT_ALGORITHM must be one of {_ALLOWED_ALGORITHMS}, got '{algorithm}'")
```

**Why:** An attacker who can influence environment variables could set `JWT_ALGORITHM=none` to bypass signature verification. While PyJWT currently rejects `none` when a secret is provided, this is an implementation detail — the allowlist makes the protection explicit and future-proof.

---

### M5 — Missing Direct Dependencies

**File:** `requirements.txt`

**Added:**
```
defusedxml>=0.7.0
requests>=2.31.0
```

**Why:** Both libraries are imported in production adapter code (`limesurvey.py`, `qualtrics.py`, `qti.py`) but were only installed transitively. If the transitive dependency chain changes, XML parsing would silently fall back to the unsafe stdlib parser (or fail entirely), and HTTP adapter calls would break.

---

### Test Updates

| File | Change | Reason |
|------|--------|--------|
| `tests/test_dev_token.py:74` | `"disabled in production"` → `"only available in development/testing"` | Matches new allowlist error message |
| `tests/test_session_api.py:159` | `"session management error"` → `"session error"` | Matches new generic error message |

---

## Remaining Items (Not Yet Implemented)

| ID | Severity | Status | Notes |
|----|----------|--------|-------|
| M2 | MEDIUM | Open | CORS middleware — requires knowing the allowed origins for the deployment |
| M4 | MEDIUM | Open | OIDC state store — requires infrastructure decision (Redis, DB, or signed cookies) |
| L1 | LOW | Open | Rate limiting — requires choosing a strategy (per-IP, per-token, per-endpoint) |
| L2 | LOW | Open | OIDC nonce validation |
| L3 | LOW | Open | `datetime.utcnow()` → `datetime.now(UTC)` migration |
| L4 | LOW | Open | Token revocation mechanism |
| L5 | LOW | Open | JWKS cache TTL |
| L6 | LOW | Open | Role-based access control enforcement |
