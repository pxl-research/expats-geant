# Cryptography Inventory

This document inventories the cryptographic primitives, libraries, and key
material used by Expats. It exists for security review (OWASP ASVS V11),
compliance traceability (DPIA artefact), and operator hardening guidance.

Last updated: 2026-06-02 — track changes via the commit history of this file.

## Summary

| Use | Algorithm | Library | Key material | Notes |
|---|---|---|---|---|
| Platform JWT signing | HMAC-SHA256 (HS256, configurable) | `PyJWT` | `JWT_SECRET` env var | Shared between Cue and Shape; rotate by re-deploying with a new secret (invalidates outstanding tokens) |
| OIDC ID token verification | RS256 (per IdP JWKS) | `Authlib` / `PyJWT` | IdP's published JWKS | Verified against `OIDC_ISSUER_URL` discovery document |
| OIDC PKCE code challenge | SHA-256 (S256) | `m_shared/auth/oauth.py` (stdlib `hashlib`) | per-flow ephemeral verifier | Added per audit finding V10-F1 (2026-04-15) |
| OIDC state and nonce | Cryptographic random (256 bits) | stdlib `secrets.token_urlsafe` | per-flow ephemeral | Used to prevent CSRF and ID-token replay |
| Session ID derivation | SHA-256 truncated to 16 hex chars (64 bits) | stdlib `hashlib` | derived from JWT | Deterministic from a given token → enables implicit resumption without server-side state |
| HTML sanitization of LLM output | Allow-list HTML parser | `nh3` (Rust Ammonia binding) | n/a | Added per audit finding V1-F1 (2026-04-15) |
| Inbound TLS | TLS 1.2+ recommended | terminator (nginx / Caddy / Cloudflare / etc.) | operator-managed | **Deployer responsibility**; not provided by application |
| Outbound TLS (LLM / OIDC / external API calls) | TLS 1.2+ as offered by remote | `httpx` (uses system trust store via `certifi` / OpenSSL) | n/a | `validate_api_url` enforces `https://` scheme for external survey-platform APIs |
| Password storage | n/a — delegated to Keycloak | Keycloak (PBKDF2-SHA256 by default) | Keycloak realm DB | Application never handles passwords directly |

## Detailed notes

### JWT (platform tokens)

- **Algorithm**: `HS256` by default, configurable via `JWT_ALGORITHM`.
  HS256 is symmetric and uses `JWT_SECRET` as the shared secret. The default
  is acceptable for a single-service-cluster deployment; if Cue and Shape
  ever run on separate trust domains, switch to an asymmetric algorithm
  (`RS256` / `EdDSA`) so the secret never needs to be shared.
- **Claims set**: `user_id`, `session_id` (optional), `org` (optional),
  `roles` (optional), `exp`, `iat`.
- **Secret strength**: at least 256 bits of entropy. The startup-checks
  guard (`m_shared/utils/startup_checks.py`) refuses to start the API in
  `ENVIRONMENT=production` when `JWT_SECRET` matches a known placeholder.

### OIDC flow

- **Authorisation Code + PKCE (S256)**: implemented in
  `m_shared/auth/oauth.py`. `code_verifier` is 32 random bytes via
  `secrets.token_urlsafe(32)`; `code_challenge` is the URL-safe base64 of
  `SHA256(code_verifier)`.
- **`state` and `nonce`**: each 32 bytes from `secrets.token_urlsafe`,
  bound to the pending flow in an in-memory dict with a 10-minute TTL.
  Single-worker only (audit finding V10-F2 — multi-worker deployment
  needs an external store such as Redis).
- **ID-token verification**: signature checked against the IdP's JWKS
  (RS256 in the default Keycloak realm); `iss`, `aud`, `exp`, `iat`, `nonce`
  are all validated.

### Session IDs

- Derived from the JWT bearer token via `SHA-256(token)` truncated to the
  first 16 hex characters (64 bits of entropy).
- 64 bits is below the typical 128-bit recommendation for session
  identifiers because session IDs in this system are **not** independent
  secrets — they are deterministic projections of an already-secret JWT.
  An attacker who can guess a session ID can equally guess a JWT, which is
  computationally infeasible at HS256 strength.

### Random number generation

All security-sensitive randomness uses Python's `secrets` module (CSPRNG,
backed by `os.urandom`). No `random.random()` / `uuid4()` paths are used
for tokens, nonces, or state values.

### What this project deliberately does NOT do

- **No application-level encryption at rest.** Session data, vector
  indices, and audit logs are stored as plaintext files. Disk-level
  encryption (LUKS, FileVault, cloud-provider equivalents) is the
  deployer's responsibility — documented in `docs/OPERATOR_RUNBOOK.md`.
- **No client-side encryption of uploaded artefacts.** Documents are
  decrypted, parsed, embedded, and stored server-side.
- **No homomorphic / federated / privacy-preserving ML.** Out of scope for
  the PoC.
- **No HSM / KMS integration.** Secrets are read from environment
  variables; deployers wanting envelope encryption should mount secrets
  from a secret manager into the container env at runtime.

### Crypto-related dependencies

Direct or transitive cryptographic libraries (subject to pinning policy in
`requirements.txt`):

| Library | Used for | Source of trust |
|---|---|---|
| `PyJWT` | JWT signing / verification | Authoritative for HS*/RS*/ES*/EdDSA JWTs |
| `Authlib` | OIDC discovery, token exchange, JWKS | Pulls cryptographic primitives from `cryptography` |
| `cryptography` (transitive) | RSA / ECDSA / X.509 backing for the above | Maintained by PyCA, FIPS-validatable backends available |
| `nh3` (Ammonia) | HTML sanitization | Allow-list parser; not a cryptographic primitive but security-relevant |
| `httpx` | TLS verification of outbound calls | Uses `certifi` CA bundle / system trust store |
| `hashlib`, `secrets`, `hmac` (stdlib) | SHA-256, CSPRNG, constant-time compare | Python stdlib |

## Recommended operator hardening

- Set `JWT_SECRET` to at least 32 random bytes (`openssl rand -base64 32`)
  and never reuse it across environments.
- Enforce TLS 1.2 minimum at the inbound terminator; disable TLS 1.0/1.1.
- Enable HSTS at the terminator with `max-age >= 15552000` and
  `includeSubDomains`.
- Configure Keycloak with a password policy (length, complexity, breach
  detection) and MFA — both noted as audit findings V6-F1 / V6-F2.
- Rotate `JWT_SECRET` periodically (the rotation invalidates all
  outstanding platform JWTs — coordinate with users).
- For multi-worker deployments, replace the in-memory OIDC state store
  with a shared backend (Redis or DB) before scaling.

## References

- [OWASP ASVS 5.0.0 audit results](SECURITY_AUDIT_OWASP_2_RESULTS.md) —
  Chapter V11 (Cryptography), Chapter V10 (OAuth/OIDC)
- [Operator Runbook](OPERATOR_RUNBOOK.md) — operational hardening guidance
- [Security Policy](../SECURITY.md) — vulnerability reporting and scope
