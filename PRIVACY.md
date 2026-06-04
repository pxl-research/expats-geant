# Privacy Notice

This document explains how the Expats software processes personal data and how
data subjects can exercise their rights under the EU General Data Protection
Regulation (GDPR, Regulation (EU) 2016/679).

It is part of the project's commitment to privacy-by-default and GDPR-aligned
governance (see §2.8 of the GÉANT Innovation Programme application).

## Scope of This Notice

This notice covers the Expats **software** as published in this repository.

Each institution that deploys Expats operates its own instance and is the
**data controller** for the personal data processed in that instance.
Institution-specific privacy notices, lawful bases, retention policies, and
data-subject contact points are the responsibility of the deploying institution.

**PXL University College** is the data controller only for:

- The PXL-hosted demo and pilot instance(s) operated by the project team

## Data the Software Processes

Expats is designed for data minimisation. By default, an instance processes:

- **Authentication data** — OIDC/JWT identifiers (subject ID, email, name as
  asserted by the identity provider; institutional SSO claims)
- **Session data** — a per-user session identifier and minimal metadata
  (creation time, TTL, consent flag, language/style preferences)
- **Uploaded artefacts** — documents, text, or URL content the user provides;
  text is extracted, chunked, and embedded into a per-session vector store
- **Conversation history** — chat messages within a session, used for
  context in the next turn
- **Suggestions and edits** — the AI's draft answers, citations, and any user
  acceptance/edit/rejection events
- **Audit logs** — events recorded for compliance and operational integrity
  (upload, suggestion, edit, session start/end, consent acceptance)

The software does **not**:

- Profile users across sessions
- Train AI models on user data
- Share data between sessions or between users (per-session isolation is
  enforced at the storage layer)

## Retention

Retention is configurable per deployment. Operational defaults, the
corresponding environment variables (`SESSION_TTL_HOURS`,
`AUDIT_RETENTION_DAYS`), and the GDPR alignment guidance live in
[`docs/OPERATOR_RUNBOOK.md` §1.3 "Data Retention"](docs/OPERATOR_RUNBOOK.md#13-data-retention).

Briefly:

- Sessions and their derived data (uploaded documents, vector indices) are
  deleted automatically when the session expires
- Audit reports are kept for the configured period and then permanently
  deleted; users may download their own report at any time during that window
- A right-to-be-forgotten (RTBF) deletion removes a user's sessions, vector
  stores, and audit reports across the deployment

## Lawful Basis

- **PXL-hosted demo/pilot**: explicit informed consent of the participant,
  captured at session start. Participation is voluntary; participants may
  withdraw at any time without consequence
- **Partner-institution instances**: determined by each controlling
  institution. Consent is the expected default; legitimate interest may apply
  for internal administrative use cases, subject to a balancing test

Pilot operators may use the
[Participant Information Sheet template](docs/PARTICIPANT_INFORMATION_SHEET_TEMPLATE.md)
and [Informed Consent Form template](docs/INFORMED_CONSENT_TEMPLATE.md)
as a starting point. Both are based on the European Commission's Horizon
Europe model and should be reviewed by your DPO and ethics committee before
use.

## Data Subject Rights

Under GDPR you have the right to:

- **Access** the personal data we process about you
- **Rectify** inaccurate or incomplete data
- **Erasure** ("right to be forgotten") of your data
- **Restriction** of processing
- **Portability** of data you provided
- **Object** to processing, including for direct decision-making
- **Withdraw consent** at any time, without affecting the lawfulness of prior
  processing

### Where to direct your request

- For data held by **the institution running your instance** of Expats:
  contact that institution's Data Protection Officer. PXL cannot action
  requests on data we do not control
- For data held by **the PXL-hosted demo/pilot**, or for questions about the
  software's privacy design: <dpo@pxl.be>

### Right to lodge a complaint

You have the right to lodge a complaint with a supervisory authority. The
Belgian supervisory authority is the
**Gegevensbeschermingsautoriteit / Autorité de protection des données (GBA/APD)**:

- Web: <https://www.dataprotectionauthority.be>
- Address: Rue de la Presse 35, 1000 Brussels, Belgium

For other EU/EEA jurisdictions, see the
[European Data Protection Board's list of authorities](https://edpb.europa.eu/about-edpb/about-edpb/members_en).

## Third-Party Processors

When the software calls an external service, the operator's choice of provider
determines the processor relationship. Common cases:

- **LLM providers** (e.g. OpenRouter, OpenAI, EU-hosted alternatives): act as
  processors. Expats sends the minimum necessary data per request (the user's
  question and retrieved passages). Provider-side training on prompts is
  disabled where the provider allows it (API-mode default for OpenAI and
  OpenRouter as of 2026)
- **Vector store (ChromaDB)**: runs locally inside the deployment; no
  third-party processor relationship
- **Identity provider (Keycloak)**: runs locally inside the reference
  deployment; institutions may federate with external IdPs under their own
  arrangements

If a chosen provider is established outside the EU/EEA, the deploying
institution is responsible for the appropriate transfer safeguard (Standard
Contractual Clauses, adequacy decision, or equivalent). The PXL-hosted demo
prefers EU-hosted models where feasible.

## Special-Category Data

Expats discourages the upload of special-category data (Article 9 GDPR — e.g.
health, biometrics, political opinions, religious beliefs, sexual orientation,
trade-union membership) and includes guidance and filters intended to reduce
accidental processing.

Operators should configure these controls per their risk appetite and instruct
respondents not to upload special-category data unless a specific lawful basis
and additional safeguards are in place. See `docs/OPERATOR_RUNBOOK.md` for the
GDPR checklist.

## Data Protection Impact Assessment

A DPIA is being prepared for the PoC scope. A redacted summary will be made
available on request via <dpo@pxl.be> once finalised.

## Security

Privacy depends on security. See [`SECURITY.md`](SECURITY.md) for the project's
security posture and vulnerability-reporting process. The OWASP ASVS 5.0.0
audit results are in
[`docs/SECURITY_AUDIT_OWASP_2_RESULTS.md`](docs/SECURITY_AUDIT_OWASP_2_RESULTS.md).

## Changes to This Notice

Material changes will be reflected in the project changelog and the commit
history of this file. The current version of this document is the version on
the `main` branch of this repository.
