# IDF Form — Answers

## Software Documentation

**Do you have software documentation available?**

**Technical documentation:**
Architecture specs (`openspec/specs/`), REST API references for [Cue](CUE_API.md) and [Shape](SHAPE_API.md), [data model](DATA_MODEL.md) with Mermaid diagrams, [deployment guide](DEPLOYMENT.md) (Docker setup, env vars, production config), [operator runbook](OPERATOR_RUNBOOK.md), [adapter guide](ADAPTERS.md) for writing custom survey platform integrations, and per-module READMEs. Code follows PEP 8 with inline documentation.

**User documentation:**
[Survey design guidelines](SURVEY_DESIGN_GUIDELINES.md), [style guide template](STYLE_GUIDE_TEMPLATE.md) for institutional customisation, and built-in interactive API docs (Swagger UI at `/docs` on each service). Pilot UIs are self-explanatory HTMX-based interfaces; formal user manuals and training materials are planned for the dissemination phase (WP4, May–Jun 2026).

**Project/administrative documentation:**
[Project plan](PROJECT_PLAN.md) with milestones, team, risks, and course adjustments; OpenSpec change proposals (`openspec/changes/`) with full design rationale and audit trail; [security audit results](SECURITY_AUDIT_OWASP_2_RESULTS.md) (OWASP-based); [testing guide](TESTING.md) with conformance suite; version history via Git with conventional commit prefixes; known limitations and scope adjustments documented in the project plan.

---

## Data Usage

**Does the software use data?**

Yes, the software processes data in several categories:

**Personal data:**
The platform processes user-uploaded documents (PDF, DOCX, TXT, Markdown) for RAG-based answer suggestion, and handles user identity via OIDC/JWT (Keycloak). However, it is designed with **privacy by default**: session-based data isolation, automatic TTL-based cleanup (default 24h), no user profiling or cross-session tracking, consent capture at session start, and audit trails. The architecture is GDPR-aligned by design. A formal GDPR checklist has not yet been filled in — this is planned as part of the pilot and close-out phase (WP3/WP4).

**Open data:**
The software does not consume or redistribute open datasets. Survey content is created by administrators or uploaded by respondents — it is institutional data, not open data.

**Data from third parties:**
Survey questions and responses may be exchanged with external survey platforms (LimeSurvey, Qualtrics, SurveyMonkey) via platform adapters, but only when explicitly configured by the operator. LLM inference is routed through **OpenRouter** (primary) or any OpenAI-compatible endpoint — user prompts and document fragments are sent to these providers for processing. No formal data processing agreements have been closed yet with LLM providers; operators can mitigate this by configuring a local/EU-hosted LLM endpoint (the architecture supports any OpenAI-compatible provider). Provider configuration and data routing options are documented in the [operator runbook](OPERATOR_RUNBOOK.md).

---

## Deployment

**How will the software be implemented or deployed?**

Containerised server-side application. The platform is deployed as a set of five Docker containers orchestrated via Docker Compose: two REST API backends (Cue, Shape), two browser-based frontends (Cue UI, Shape UI), and a bundled identity provider (Keycloak). No special hardware, client-side installation, or native apps are required — end users access the system through a standard web browser.

Deployment targets institutional server infrastructure (on-premise or cloud-hosted VM). The operator provides an API key for an LLM provider (OpenRouter, OpenAI-compatible, or a local model endpoint) and configures environment variables. The entire stack starts with a single `docker-compose up` command. Designed for institutional self-hosting within the European R&E community, with OIDC-based authentication for integration into existing identity federations.

---

## Open Source and Proprietary Dependencies

**Does the invention incorporate or rely on any open source software (OSS) components, libraries, or frameworks?**

Yes, the software is built entirely on open-source components:

*Runtime & infrastructure:*

| Package | Version | Purpose | License |
|---|---|---|---|
| Python | 3.12 | Runtime language | PSF |
| Docker | 29.4.1 | Containerisation | Apache-2.0 |
| Docker Compose | 5.1.3 | Container orchestration | Apache-2.0 |
| Keycloak | 26.0 | Identity provider (OIDC) | Apache-2.0 |

*Web framework & networking:*

| Package | Version | Purpose | License |
|---|---|---|---|
| fastapi | 0.128.0 | Web framework (REST APIs & UIs) | MIT |
| uvicorn | 0.40.0 | ASGI server | BSD-3-Clause |
| httpx | 0.28.1 | Async HTTP client | BSD-3-Clause |
| requests | 2.32.5 | HTTP client (adapters) | Apache-2.0 |
| python-multipart | 0.0.22 | Form/file upload parsing | Apache-2.0 |

*AI & data processing:*

| Package | Version | Purpose | License |
|---|---|---|---|
| openai | 2.16.0 | LLM client (OpenRouter/OpenAI-compatible) | Apache-2.0 |
| chromadb | 1.4.1 | Vector database (semantic search/RAG) | Apache-2.0 |
| markitdown | 0.1.4 | Document parsing (PDF, DOCX, PPTX, XLSX) | MIT |
| tiktoken | 0.12.0 | Token counting | MIT |

*Frontend & templating:*

| Package | Version | Purpose | License |
|---|---|---|---|
| Jinja2 | 3.1.6 | HTML templating (frontends) | BSD-3-Clause |
| HTMX | — | Frontend interactivity | BSD-2-Clause |
| Markdown | 3.10.2 | Markdown-to-HTML rendering (Shape UI) | BSD-3-Clause |

*Authentication & security:*

| Package | Version | Purpose | License |
|---|---|---|---|
| PyJWT | 2.11.0 | JWT authentication | MIT |
| Authlib | 1.6.9 | OIDC authentication | BSD-3-Clause |
| defusedxml | 0.7.1 | Secure XML parsing | PSF |
| slowapi | 0.1.9 | Rate limiting | MIT |
| nh3 | 0.3.4 | HTML sanitisation | MIT |
| itsdangerous | 2.2.0 | Signed session tokens | BSD-3-Clause |

*Data validation & utilities:*

| Package | Version | Purpose | License |
|---|---|---|---|
| pydantic | 2.12.5 | Data validation (via FastAPI) | MIT |
| tqdm | 4.67.2 | Progress bars | MPL-2.0 AND MIT |

*Development & testing (not shipped):*

| Package | Version | Purpose | License |
|---|---|---|---|
| pytest | 9.0.2 | Test framework | MIT |
| pytest-mock | 3.15.1 | Test mocking | MIT |
| pytest-cov | 7.0.0 | Test coverage | MIT |
| pytest-asyncio | 1.3.0 | Async test support | Apache-2.0 |
| respx | 0.22.0 | HTTP request mocking | BSD-3-Clause |
| ruff | 0.15.2 | Linting & formatting | MIT |
| mypy | 1.19.1 | Static type checking | MIT |
| types-requests | 2.32.4 | Type stubs for requests | Apache-2.0 |
| pre-commit | 4.5.1 | Git hook management | MIT |

All dependencies use permissive open-source licenses (MIT, Apache 2.0, BSD, PSF) that are compatible with the project's PolyForm Noncommercial 1.0.0 license.

**Proprietary dependencies:**
The platform relies on third-party **LLM inference providers** (OpenRouter, OpenAI, or similar) as a cloud service for generating suggestions. These are proprietary commercial APIs consumed over HTTP — no proprietary software is embedded or installed. Operators can eliminate this dependency by configuring a self-hosted open-source LLM endpoint (e.g. Ollama, vLLM).
