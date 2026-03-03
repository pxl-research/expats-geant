# Change: Add Security Event Logging

## Why

No structured logging exists in the auth layer (`jwt_handler.py`, `middleware.py`, `oauth.py`). Security-relevant events — expired tokens, invalid OIDC state, ID token failures — are raised as exceptions but never recorded. This makes it impossible to detect abuse patterns, misconfiguration, or integration issues after the fact. Logs must persist across server restarts to be useful for operational review.

## What Changes

- Add `logger = logging.getLogger(__name__)` to `jwt_handler.py`, `middleware.py`, and `oauth.py`
- Log security events at appropriate levels (`WARNING` for expected failures, `ERROR` for unexpected/internal failures, `INFO` for successful OIDC login)
- Configure a `RotatingFileHandler` writing to `logs/security.log` in `run_api.py` (5 MB × 3 backups)
- Add `logs/` to `.gitignore`
- Add ADDED requirement to the `auth-security` spec

## What Gets Logged

**`middleware.py`** — one log per rejected request:
- Missing Bearer token → `WARNING`
- Expired token → `WARNING` (includes path)
- Invalid/malformed token → `WARNING` (includes path + reason)
- Missing required claims (`session_id`, `user_id`) → `WARNING`

**`jwt_handler.py`** — token lifecycle:
- Token creation failure (missing `JWT_SECRET`) → `ERROR`
- Token expired on validation → `WARNING`
- Invalid signature / malformed token → `WARNING`

**`oauth.py`** — OIDC flow:
- Invalid or expired OIDC state parameter → `WARNING`
- ID token validation failure (wrong `iss`, `aud`, expired, bad signature) → `WARNING`
- Missing `sub` claim → `WARNING`
- OIDC provider unreachable → `ERROR`
- Successful OIDC login (normalized `user_id`) → `INFO`

## Impact

- Affected specs: `auth-security`
- Affected code: `m_shared/auth/jwt_handler.py`, `m_shared/auth/middleware.py`, `m_shared/auth/oauth.py`, `run_api.py`
- New file: `logs/security.log` (runtime, gitignored)
- No breaking changes; no API surface changes
