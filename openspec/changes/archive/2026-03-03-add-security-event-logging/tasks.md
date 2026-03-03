## 1. Logging Infrastructure

- [x] 1.1 Add `RotatingFileHandler` for `logs/security.log` (5 MB × 3 backups) to `run_api.py`
- [x] 1.2 Add `logs/` to `.gitignore`

## 2. jwt_handler.py

- [x] 2.1 Add `logger = logging.getLogger(__name__)` at module level
- [x] 2.2 Log `ERROR` on token creation failure (missing `JWT_SECRET`)
- [x] 2.3 Log `WARNING` on `TokenExpiredError` during validation
- [x] 2.4 Log `WARNING` on `TokenInvalidError` / malformed token during validation

## 3. middleware.py

- [x] 3.1 Add `logger = logging.getLogger(__name__)` at module level
- [x] 3.2 Log `WARNING` on missing Bearer token (include request path)
- [x] 3.3 Log `WARNING` on expired token (include request path)
- [x] 3.4 Log `WARNING` on invalid/malformed token (include request path + reason)
- [x] 3.5 Log `WARNING` on missing required claims (`session_id`, `user_id`)

## 4. oauth.py

- [x] 4.1 Add `logger = logging.getLogger(__name__)` at module level
- [x] 4.2 Log `WARNING` on invalid or expired OIDC state parameter
- [x] 4.3 Log `WARNING` on ID token validation failure (include failure reason)
- [x] 4.4 Log `WARNING` on missing `sub` claim in ID token
- [x] 4.5 Log `ERROR` on OIDC provider unreachable
- [x] 4.6 Log `INFO` on successful OIDC login (include normalized `user_id`, omit sensitive claims)

## 5. Tests

- [x] 5.1 Add log-capture tests to `tests/test_auth.py` using pytest `caplog`
  - [x] 5.1a Expired token → WARNING logged
  - [x] 5.1b Invalid token → WARNING logged
  - [x] 5.1c Missing secret on creation → ERROR logged
- [x] 5.2 Add log-capture tests to `tests/test_oauth.py` using pytest `caplog`
  - [x] 5.2a Invalid OIDC state → WARNING logged
  - [x] 5.2b ID token validation failure → WARNING logged
  - [x] 5.2c OIDC provider unreachable → ERROR logged
  - [x] 5.2d Successful OIDC login → INFO logged
- [x] 5.3 Verify no sensitive data (secrets, full tokens, raw `sub` values) appears in log output
