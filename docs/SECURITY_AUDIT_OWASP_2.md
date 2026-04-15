# OWASP ASVS 5.0.0 Security Audit Reference

**Source:** OWASP Application Security Verification Standard, Version 5.0.0 (May 2025)
**Purpose:** Summary of all 17 verification chapters for use in our security audit of the expat-geant platform.

## Overview

ASVS 5.0.0 contains approximately 350 security requirements across 17 chapters. Requirements are assigned to three levels:

- **Level 1 (~20% of requirements):** Critical first-layer defenses; minimum starting point for any application.
- **Level 2 (~50% of requirements):** Standard security practices; the target for most applications.
- **Level 3 (~30% of requirements):** Advanced, high-assurance controls for the most sensitive systems.

Requirements use the identifier format `<chapter>.<section>.<requirement>` (e.g., `v5.0.0-1.2.5`).

---

## V1 Encoding and Sanitization

**Objective:** Prevent vulnerabilities from unsafe processing of untrusted data by ensuring correct output encoding, escaping, and sanitization.

### Sections

| Section | Focus | Key Requirements |
|---------|-------|-----------------|
| V1.1 Encoding & Sanitization Architecture | Canonical decoding, output encoding order | 1.1.1 (L2): Single decode/unescape; 1.1.2 (L2): Output encoding as final step |
| V1.2 Injection Prevention | Context-specific output encoding | 1.2.1 (L1): HTTP/HTML/XML encoding; 1.2.2 (L1): URL encoding; 1.2.3 (L1): JS/JSON encoding; 1.2.4 (L1): Parameterized DB queries; 1.2.5 (L1): OS command injection protection |
| V1.3 Sanitization | Removing dangerous content | 1.3.1 (L1): HTML sanitization; 1.3.2 (L1): No eval/dynamic code; 1.3.6 (L2): SSRF protection; 1.3.7 (L2): Template injection prevention |
| V1.4 Memory, String, Unmanaged Code | Buffer/overflow protections | 1.4.1-1.4.3 (L2): Memory-safe ops, integer overflow checks |
| V1.5 Safe Deserialization | Prevent deserialization attacks | 1.5.1 (L1): Restrictive XML parser config (XXE); 1.5.2 (L2): Allowlist for deserialization types |

---

## V2 Validation and Business Logic

**Objective:** Ensure input matches business/functional expectations, business logic is sequential and tamper-proof, and automated abuse is prevented.

### Sections

| Section | Focus | Key Requirements |
|---------|-------|-----------------|
| V2.1 Documentation | Define validation rules | 2.1.1 (L1): Document input validation rules; 2.1.3 (L2): Document business logic limits |
| V2.2 Input Validation | Server-side enforcement | 2.2.1 (L1): Validate against allow lists/patterns/ranges; 2.2.2 (L1): Enforce at trusted service layer |
| V2.3 Business Logic Security | Prevent logic exploitation | 2.3.1 (L1): Sequential step enforcement; 2.3.3 (L2): Atomic transactions; 2.3.4 (L2): Resource locking |
| V2.4 Anti-automation | Rate limiting, abuse prevention | 2.4.1 (L2): Anti-automation controls for sensitive functions |

---

## V3 Web Frontend Security

**Objective:** Protect against browser-based attacks. Not applicable to machine-to-machine APIs.

### Sections

| Section | Focus | Key Requirements |
|---------|-------|-----------------|
| V3.1 Documentation | Browser security feature expectations | 3.1.1 (L3): Document HTTPS, HSTS, CSP expectations |
| V3.2 Content Interpretation | Prevent content type confusion | 3.2.1 (L1): Prevent incorrect context rendering; 3.2.2 (L1): Safe text rendering |
| V3.3 Cookie Setup | Secure cookie configuration | 3.3.1 (L1): Secure attribute + __Host- prefix; 3.3.2 (L2): SameSite; 3.3.4 (L2): HttpOnly for non-JS cookies |
| V3.4 Security Headers | HTTP response security headers | 3.4.1 (L1): HSTS with 1yr max-age; 3.4.2 (L1): CORS allowlist; 3.4.3 (L2): CSP; 3.4.4 (L2): X-Content-Type-Options: nosniff; 3.4.5 (L2): Referrer-Policy; 3.4.6 (L2): frame-ancestors |
| V3.5 Origin Separation | CSRF and cross-origin protections | 3.5.1 (L1): CSRF tokens or non-CORS-safelisted headers; 3.5.2 (L1): CORS preflight enforcement; 3.5.3 (L1): Safe HTTP methods for sensitive ops |
| V3.6 External Resource Integrity | SRI for external assets | 3.6.1 (L3): SRI for CDN-hosted assets |
| V3.7 Other Browser Security | Deprecated tech, redirects | 3.7.1 (L2): No deprecated client-side tech; 3.7.2 (L2): Redirect allowlist |

---

## V4 API and Web Service

**Objective:** Secure API-specific configurations and mechanisms for applications exposing JSON, XML, or GraphQL APIs.

### Sections

| Section | Focus | Key Requirements |
|---------|-------|-----------------|
| V4.1 Generic Web Service Security | HTTP hygiene | 4.1.1 (L1): Correct Content-Type; 4.1.3 (L2): Prevent header spoofing (X-Real-IP, X-Forwarded-*) |
| V4.2 HTTP Message Structure | Request smuggling prevention | 4.2.1 (L2): Proper HTTP boundary determination |
| V4.3 GraphQL | Query cost/depth limiting | 4.3.1 (L2): Query depth/cost limiting; 4.3.2 (L2): Disable introspection in production |
| V4.4 WebSocket | Secure WS communication | 4.4.1 (L1): WSS (TLS) required; 4.4.2 (L2): Origin header validation |

---

## V5 File Handling

**Objective:** Prevent DoS, unauthorized access, and storage exhaustion from file operations.

### Sections

| Section | Focus | Key Requirements |
|---------|-------|-----------------|
| V5.1 Documentation | Document allowed file types/sizes | 5.1.1 (L2): Define permitted types, extensions, max sizes |
| V5.2 Upload and Content | Validate uploaded files | 5.2.1 (L1): File size limits; 5.2.2 (L1): Extension + magic byte validation; 5.2.3 (L2): Compressed file size checks |
| V5.3 File Storage | Prevent execution of uploaded files | 5.3.1 (L1): No server-side execution of uploads; 5.3.2 (L1): Use generated filenames, sanitize user paths |
| V5.4 File Download | Safe file serving | 5.4.1 (L2): Server-set filenames in Content-Disposition; 5.4.3 (L2): Antivirus scanning of untrusted files |

---

## V6 Authentication

**Objective:** Verify identity claims, resist impersonation, and prevent password interception/recovery.

### Sections

| Section | Focus | Key Requirements |
|---------|-------|-----------------|
| V6.1 Documentation | Document auth controls | 6.1.1 (L1): Document rate limiting, anti-brute-force; 6.1.2 (L2): Context-specific password blocklist |
| V6.2 Password Security | Password policy | 6.2.1 (L1): Min 8 chars (15 recommended); 6.2.4 (L1): Check against top 3000 breached passwords; 6.2.5 (L1): No composition rules; 6.2.8 (L1): No password truncation; 6.2.9 (L2): Allow 64+ chars; 6.2.12 (L2): Check breached password sets |
| V6.3 General Auth Security | Brute force, MFA | 6.3.1 (L1): Credential stuffing/brute-force controls; 6.3.2 (L1): No default accounts; 6.3.3 (L2): MFA required (hardware-based for L3) |
| V6.4 Factor Lifecycle | Secure recovery | 6.4.1 (L1): Initial passwords expire quickly; 6.4.2 (L1): No security questions; 6.4.3 (L2): Password reset doesn't bypass MFA |
| V6.5 MFA Requirements | OTP/TOTP/lookup secrets | 6.5.1-6.5.5 (L2): Single-use codes, CSPRNG generation, time-limited OTPs |
| V6.6 Out-of-Band Auth | Push/SMS/phone authentication | 6.6.1 (L2): Phone/SMS only with validated number + stronger alternative offered; 6.6.3 (L2): Rate-limit OOB auth |
| V6.7 Cryptographic Auth | FIDO/smart cards | 6.7.1-6.7.2 (L3): Tamper-protected certs, 64-bit nonces |
| V6.8 Identity Provider | IdP integration security | 6.8.1 (L2): Cross-IdP identity spoofing prevention; 6.8.2 (L2): Validate JWT/SAML signatures; 6.8.4 (L2): Verify IdP auth strength claims (acr, amr) |

---

## V7 Session Management

**Objective:** Sessions must be unique, securely generated, invalidated on timeout/logout, and resistant to hijacking.

### Sections

| Section | Focus | Key Requirements |
|---------|-------|-----------------|
| V7.1 Documentation | Document session design | 7.1.1 (L2): Document inactivity + absolute timeouts; 7.1.2 (L2): Document concurrent session policy |
| V7.2 Fundamental Security | Token generation | 7.2.1 (L1): Server-side token verification; 7.2.2 (L1): Dynamic tokens (not static API keys); 7.2.3 (L1): CSPRNG with 128-bit entropy; 7.2.4 (L1): New token on auth |
| V7.3 Session Timeout | Inactivity and absolute limits | 7.3.1-7.3.2 (L2): Inactivity + absolute timeout per documented policy |
| V7.4 Session Termination | Logout and cleanup | 7.4.1 (L1): Full invalidation on logout; 7.4.2 (L1): Terminate sessions on account disable; 7.4.3 (L2): Terminate all sessions on password change |
| V7.5 Defenses Against Abuse | Re-auth for sensitive ops | 7.5.1 (L2): Re-auth before changing sensitive account attributes; 7.5.2 (L2): Users can view/terminate active sessions |
| V7.6 Federated Re-auth | SSO session coordination | 7.6.1-7.6.2 (L2): Coordinate session lifetimes with IdP |

---

## V8 Authorization

**Objective:** Enforce Principle of Least Privilege (POLP) with function-level, data-specific, and field-level access controls.

### Sections

| Section | Focus | Key Requirements |
|---------|-------|-----------------|
| V8.1 Documentation | Document authorization rules | 8.1.1 (L1): Document function + data-level access rules; 8.1.2 (L2): Field-level access rules |
| V8.2 General Design | Granular access control | 8.2.1 (L1): Function-level access restrictions; 8.2.2 (L1): Data-specific access (prevents IDOR/BOLA); 8.2.3 (L2): Field-level access (prevents BOPLA) |
| V8.3 Operation Level | Enforcement at trusted layer | 8.3.1 (L1): Server-side enforcement (not client JS) |
| V8.4 Other Considerations | Multi-tenant, admin | 8.4.1 (L2): Cross-tenant isolation |

---

## V9 Self-contained Tokens

**Objective:** Ensure JWTs and similar self-contained tokens are signed, validated, and scoped correctly.

### Sections

| Section | Focus | Key Requirements |
|---------|-------|-----------------|
| V9.1 Source and Integrity | Token signing/validation | 9.1.1 (L1): Validate digital signature/MAC; 9.1.2 (L1): Algorithm allowlist (no 'None'); 9.1.3 (L1): Key material from trusted sources only |
| V9.2 Token Content | Validity and audience | 9.2.1 (L1): Check nbf/exp time spans; 9.2.2 (L2): Validate token type matches purpose; 9.2.3 (L2): Validate audience (aud) claim |

---

## V10 OAuth and OIDC

**Objective:** Secure implementation of OAuth 2.0 and OpenID Connect for delegated authorization and federated authentication.

### Sections

| Section | Focus | Key Requirements |
|---------|-------|-----------------|
| V10.1 Generic OAuth/OIDC | Architectural requirements | 10.1.1 (L2): Tokens only sent to components that need them; 10.1.2 (L2): PKCE, state, nonce binding |
| V10.2 OAuth Client | Client-side protections | 10.2.1 (L2): CSRF protection on code flow; 10.2.2 (L2): Issuer mix-up defense |
| V10.3 Resource Server | Token validation at API | 10.3.1 (L2): Validate audience; 10.3.2 (L2): Enforce scope/authorization claims; 10.3.3 (L2): Identify users via iss+sub |
| V10.4 Authorization Server | AS security requirements | 10.4.1 (L1): Exact redirect URI matching; 10.4.2 (L1): Single-use auth codes; 10.4.3 (L1): Short-lived auth codes (10min max); 10.4.4 (L1): Disallow implicit/password grants; 10.4.5 (L1): Sender-constrained refresh tokens; 10.4.6 (L2): PKCE required |
| V10.5 OIDC Client | Relying party protections | 10.5.1 (L2): Nonce replay protection; 10.5.2 (L2): Unique user ID from sub claim; 10.5.3 (L2): Reject mismatched issuer metadata |
| V10.6 OpenID Provider | OP configuration | 10.6.1 (L2): Allowed response modes; 10.6.2 (L2): Forced logout protection |
| V10.7 Consent Management | User consent verification | 10.7.1-10.7.3 (L2): Explicit consent, clear info, revocable permissions |

---

## V11 Cryptography

**Objective:** Use robust, industry-standard cryptographic practices with proper key management and future-proofing for post-quantum threats.

### Sections

| Section | Focus | Key Requirements |
|---------|-------|-----------------|
| V11.1 Inventory & Documentation | Crypto asset management | 11.1.1 (L2): Documented key management policy (NIST SP 800-57); 11.1.2 (L2): Maintain crypto inventory |
| V11.2 Secure Implementation | Algorithm selection | 11.2.1 (L2): Use validated/industry crypto libraries; 11.2.2 (L2): Crypto agility (swappable algorithms); 11.2.3 (L2): Min 128-bit security |
| V11.3 Encryption Algorithms | Cipher/mode requirements | 11.3.1 (L1): No ECB mode or weak padding; 11.3.2 (L1): AES-GCM or approved ciphers only; 11.3.3 (L2): Authenticated encryption |
| V11.4 Hashing & KDFs | Hash/password functions | 11.4.1 (L1): No MD5 for crypto; 11.4.2 (L2): Password hashing with approved KDF (bcrypt, argon2, scrypt); 11.4.4 (L2): Key stretching for password-derived keys |
| V11.5 Random Values | CSPRNG | 11.5.1 (L2): CSPRNG with 128-bit entropy |
| V11.6 Public Key Crypto | Key exchange, signatures | 11.6.1 (L2): Approved algorithms for key gen/signatures |
| V11.7 In-Use Data Crypto | Memory encryption | 11.7.1-11.7.2 (L3): Full memory encryption, data minimization |

---

## V12 Secure Communication

**Objective:** Encrypt data in transit between client-server and server-server using TLS with proper certificate management.

### Sections

| Section | Focus | Key Requirements |
|---------|-------|-----------------|
| V12.1 TLS Security | Protocol/cipher configuration | 12.1.1 (L1): TLS 1.2+ only (prefer 1.3); 12.1.2 (L2): Strong cipher suites with forward secrecy; 12.1.3 (L2): Validate mTLS client certificates |
| V12.2 External HTTPS | Client-facing encryption | 12.2.1 (L1): TLS for all external connections, no fallback; 12.2.2 (L1): Publicly trusted certificates |
| V12.3 Service-to-Service | Internal encryption | 12.3.1 (L2): TLS for all inbound/outbound connections; 12.3.3 (L2): Internal service TLS; 12.3.4 (L2): Trusted internal certificates |

---

## V13 Configuration

**Objective:** Secure default configuration, prevent data leakage, manage secrets properly, and harden production deployments.

### Sections

| Section | Focus | Key Requirements |
|---------|-------|-----------------|
| V13.1 Documentation | Document communication needs | 13.1.1 (L2): Document all external service dependencies |
| V13.2 Backend Communication | Service auth and access | 13.2.1 (L2): Authenticated inter-service communication; 13.2.2 (L2): Least privilege for service accounts; 13.2.3 (L2): No default credentials; 13.2.4 (L2): Outbound connection allowlist; 13.2.5 (L2): Server-side request allowlist |
| V13.3 Secret Management | Protect secrets | 13.3.1 (L2): Use a secrets vault; secrets never in source code; 13.3.2 (L2): Least privilege for secret access |
| V13.4 Unintended Info Leakage | Harden production | 13.4.1 (L1): No exposed .git/.svn folders; 13.4.2 (L2): Debug mode disabled in production; 13.4.3 (L2): No directory listings; 13.4.4 (L2): Disable HTTP TRACE; 13.4.5 (L2): Internal APIs not publicly exposed |

---

## V14 Data Protection

**Objective:** Classify sensitive data, implement appropriate protection controls, and prevent unintended data exposure.

### Sections

| Section | Focus | Key Requirements |
|---------|-------|-----------------|
| V14.1 Documentation | Data classification | 14.1.1 (L2): Classify all sensitive data with protection levels; 14.1.2 (L2): Document encryption, integrity, retention, access requirements |
| V14.2 General Data Protection | Prevent data leakage | 14.2.1 (L1): No sensitive data in URLs/query strings; 14.2.2 (L2): Prevent sensitive data caching; 14.2.3 (L2): No data sent to untrusted third parties |
| V14.3 Client-side Protection | Browser data cleanup | 14.3.1 (L1): Clear authenticated data on session end; 14.3.2 (L2): Anti-caching headers for sensitive responses; 14.3.3 (L2): No sensitive data in browser storage |

---

## V15 Secure Coding and Architecture

**Objective:** Clean architecture, dependency management, defensive coding, and safe concurrency.

### Sections

| Section | Focus | Key Requirements |
|---------|-------|-----------------|
| V15.1 Documentation | SBOM and risk documentation | 15.1.1 (L1): Remediation timeframes for 3rd-party vulnerabilities; 15.1.2 (L2): SBOM maintained; 15.1.3 (L2): Document resource-demanding functionality |
| V15.2 Architecture & Dependencies | Dependency security | 15.2.1 (L1): No components past remediation deadlines; 15.2.2 (L2): DoS defenses for resource-heavy features; 15.2.3 (L2): No test code in production |
| V15.3 Defensive Coding | Prevent common code flaws | 15.3.1 (L1): Return only required fields from data objects; 15.3.2 (L2): No open redirects to external URLs; 15.3.3 (L2): Mass assignment protection; 15.3.7 (L2): HTTP parameter pollution defense |
| V15.4 Safe Concurrency | Race conditions, thread safety | 15.4.1-15.4.4 (L3): Thread-safe shared objects, TOCTOU prevention, proper locking |

---

## V16 Security Logging and Error Handling

**Objective:** Log security-relevant events with structured metadata; protect logs; fail securely without exposing internals.

### Sections

| Section | Focus | Key Requirements |
|---------|-------|-----------------|
| V16.1 Logging Documentation | Logging inventory | 16.1.1 (L2): Document logging at each stack layer |
| V16.2 General Logging | Metadata and format | 16.2.1 (L2): Include when/who/what metadata; 16.2.2 (L2): Synchronized UTC timestamps; 16.2.5 (L2): Mask sensitive data in logs |
| V16.3 Security Events | What to log | 16.3.1 (L2): All auth operations; 16.3.2 (L2): Failed authorization; 16.3.3 (L2): Security control bypass attempts; 16.3.4 (L2): Unexpected errors and TLS failures |
| V16.4 Log Protection | Integrity and access | 16.4.1 (L2): Encode log data to prevent injection; 16.4.2 (L2): Protect from unauthorized access; 16.4.3 (L2): Transmit to separate secure system |
| V16.5 Error Handling | Fail securely | 16.5.1 (L2): Generic error messages (no stack traces/keys); 16.5.2 (L2): Circuit breakers for external failures; 16.5.3 (L2): Fail securely (no fail-open) |

---

## V17 WebRTC

**Objective:** Secure WebRTC infrastructure including TURN servers, media servers, and signaling.

### Sections

| Section | Focus | Key Requirements |
|---------|-------|-----------------|
| V17.1 TURN Server | Relay security | 17.1.1 (L2): Block reserved/internal IP addresses |
| V17.2 Media | DTLS/SRTP security | 17.2.1 (L2): DTLS key management; 17.2.2 (L2): Approved DTLS cipher suites; 17.2.3 (L2): SRTP authentication |
| V17.3 Signaling | Signaling server resilience | 17.3.1 (L2): Rate limiting for flood attacks; 17.3.2 (L2): Handle malformed messages gracefully |

---

## Relevance to Our Project

Based on our platform architecture (Python/FastAPI API-only, OIDC/Keycloak, file uploads, session-based RAG, Docker deployment), the most relevant chapters for our audit are:

| Priority | Chapter | Reason |
|----------|---------|--------|
| High | V1 Encoding & Sanitization | LLM prompt construction, JSON API responses, document processing |
| High | V2 Validation & Business Logic | API input validation, session workflow enforcement |
| High | V4 API and Web Service | REST API security, Content-Type, header spoofing |
| High | V5 File Handling | PDF/DOCX/audio uploads, file size/type validation, storage security |
| High | V6 Authentication | Keycloak/OIDC integration, password policy delegation |
| High | V7 Session Management | Ephemeral session lifecycle, TTL, cleanup |
| High | V8 Authorization | Tenant isolation, per-session data access, IDOR prevention |
| High | V9 Self-contained Tokens | JWT validation from Keycloak |
| High | V10 OAuth and OIDC | OIDC client implementation, PKCE, token handling |
| High | V13 Configuration | Secret management, Docker config, info leakage prevention |
| High | V14 Data Protection | GDPR compliance, sensitive data classification, ephemeral storage |
| High | V16 Logging & Error Handling | Audit trails, secure error responses |
| Medium | V11 Cryptography | Password hashing (delegated to Keycloak), TLS config |
| Medium | V12 Secure Communication | TLS between services, external API calls |
| Medium | V15 Secure Coding & Architecture | Dependency management, mass assignment, SBOM |
| High | V3 Web Frontend Security | cue_ui/ and shape_ui/ serve HTML templates (Jinja2) with forms, file uploads, chat, export -- cookies, CSP, CSRF, XSS all apply |
| Low | V17 WebRTC | Not applicable (no real-time communication features) |
