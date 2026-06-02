# Security Policy

This document explains how to report a vulnerability in Expats and what to
expect in return. It is part of the project's commitment to responsible
vulnerability management (see §2.8 of the GÉANT Innovation Programme
application).

## Reporting a Vulnerability

Email: **servaas.tilkin@pxl.be**
Subject prefix: `[SECURITY] Expats:`

Please include:

- Affected component (e.g. `cue_api`, `shape_ui`, a specific endpoint or file)
- Reproduction steps or proof of concept
- Impact assessment (what the issue allows an attacker to do)
- Your preferred disclosure timeline, if any

If you need encrypted communication, mention this in your initial email and we
will arrange a PGP-encrypted channel.

**Please do not**:

- Open a public GitHub issue for a suspected vulnerability
- Test against live deployments without prior written authorisation
- Access, modify, or exfiltrate data beyond what is strictly necessary to
  demonstrate the issue

## What You Can Expect

- **Acknowledgement** within 5 business days of your report
- **Triage assessment** within 10 business days (severity, scope, ownership)
- **Coordinated disclosure**: 90 days from report to public disclosure by
  default, negotiable based on severity and complexity. Critical findings may
  be fixed and disclosed sooner

We will credit reporters in release notes unless you ask us not to.

## Scope

In scope:

- The source code in this repository
- The reference `docker-compose.yml` deployment as shipped

Out of scope (responsibility of the deployer):

- Production deployments operated by partner institutions
- Keycloak realm configuration, identity-provider federation
- TLS termination, network policy, secrets management
- Operating-system and container-runtime hardening

For issues in third-party dependencies, please report upstream first, then let
us know so we can pin or patch as appropriate.

## Security Posture

Expats was audited against **OWASP ASVS 5.0.0 (May 2025) L1+L2** in April 2026.
Result: **129 of 140 applicable requirements PASS (92%), no critical
vulnerabilities found**. Full audit results, including remaining
production-hardening recommendations, are in
[`docs/SECURITY_AUDIT_OWASP_2_RESULTS.md`](docs/SECURITY_AUDIT_OWASP_2_RESULTS.md).

Known items that deployers should address as part of operational hardening
(documented in the audit, intentionally not blocking the PoC):

- HSTS header (TLS termination layer)
- Keycloak password policy and MFA enforcement
- Production secret hardening (no placeholder defaults)
- Centralised log shipping
- Anti-virus / magic-byte / zip-bomb scanning at the upload boundary

See `docs/OPERATOR_RUNBOOK.md` and `docs/DEPLOYMENT.md` for hardening guidance.

## Supported Versions

During the PoC phase (Jan–Jun 2026) only the `main` branch and the latest
tagged release receive security fixes. Older tags are not patched.

## Privacy and Data Protection

For data-protection issues, see [`PRIVACY.md`](PRIVACY.md). Privacy issues that
also have a security impact should be reported via this policy.
