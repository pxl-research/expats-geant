# EXPATS — Project Plan

**Explainable Autofill for Trustworthy Surveys**  
GÉANT Innovation Programme (GIP 2026) — PXL University College

|               |                                          |
|---------------|------------------------------------------|
| **Duration**  | January – June 2026 (6 months)           |
| **Lead**      | PXL Smart ICT, Hasselt, Belgium          |
| **Contact**   | Servaas Tilkin (servaas.tilkin@pxl.be)   |
| **Status**    | Month 4 of 6 (as of April 2026)          |

---

## 1. Project Summary

EXPATS builds two privacy-first, standalone AI modules for surveys and forms in the European R&E community:

- **Shape** — An administrator co-pilot that accelerates questionnaire design with suggestions, style guidelines, validation rules, tagging, and QTI compatibility.
- **Cue** — A respondent-side assistant that retrieves relevant passages from user-provided documents, proposes concise draft answers with citations and highlights, and explains how suggestions were derived.

Both modules are designed as embeddable, SDK-first components with clear APIs, tenant isolation, consent capture, data minimisation, and audit trails. They are containerised for on-premise deployment with OIDC-based authentication.

The project pilots both modules at PXL (and, subject to confirmation, one Belnet-connected partner), measures quality indicators (authoring time, citation accuracy, acceptance rates), and disseminates results at GÉANT TNC25 in June 2026.

---

## 2. Team

| Name               | Role                              | Allocation  |
|--------------------|-----------------------------------|-------------|
| Servaas Tilkin     | AI Development                    | 4 PM        |
| Lennert Lambrighs  | Web Development                   | 2 PM        |
| Alessio De Houwer  | Software Integration              | 2 PM      |

---

## 3. Milestones

| ID   | Milestone                              | Target     | Status              |
|------|----------------------------------------|------------|---------------------|
| M1   | Architecture & Pilot Ready             | End Jan    | ✅ Achieved          |
| M2   | SDKs v0.9 Complete                     | End Mar    | ✅ Achieved (mid-Mar)|
| M3   | Platform Integration & Pilot Live      | End April    | ⏳ In progress       |
| M4   | Dissemination & Close-Out              | End Jun    | Upcoming             |

M2 was reached ahead of schedule: both Cue and Shape SDKs (engines, APIs, and pilot UIs) were functionally complete by mid-March.

---

## 4. Work Packages

### WP1: Project Management, Communications, Pilot Ops, and TNC

**Period:** Jan – Jun (full duration) · **Lead:** PXL

Coordinate governance, schedule, risks, and budget. Manage communications and stakeholder engagement. Coordinate pilot operations (recruitment, onboarding, support). Prepare and deliver the TNC submission and demo.

| Deliverable | Description                                         | Status       |
|-------------|-----------------------------------------------------|--------------|
| D1.1        | Project handbook and communications plan             | ✅ Complete — this document (governance, schedule, team, communications, risks) |
| D1.2        | At least 1 pilot onboarded                           | ⏳ In progress |
| D1.3        | TNC submission admin pack (abstract, logistics)       | ✅ Complete   |

---

### WP2: Design and Implementation of SDKs (Cue and Shape)

**Period:** Jan – Apr · **Lead:** PXL

Specify SDK-first architecture and compliance-by-design controls. Implement MVP SDKs for Cue and Shape with privacy guardrails, audit trails, KPI instrumentation, and developer documentation.

| Deliverable | Description                                              | Status         |
|-------------|----------------------------------------------------------|----------------|
| D2.1        | Architecture and integration guide; conformance test suite | ✅ Complete — architecture in `openspec/specs/`; integration guides in `docs/CUE_API.md` + `docs/SHAPE_API.md`; conformance tests in `docs/TESTING.md` |
| D2.2        | Cue SDK v0.9 with developer docs and examples      | ✅ Complete — SDK, `cue_api/README.md`, `docs/CUE_API.md` |
| D2.3        | Shape SDK v0.9 with developer docs and examples           | ✅ Complete — SDK, `shape_api/README.md`, `docs/SHAPE_API.md` |

**What was built (Cue):**

- Document ingestion pipeline (PDF, DOCX, TXT, Markdown)
- RAG pipeline with semantic retrieval (ChromaDB) and LLM generation
- Citation system with source metadata, highlights, and evidence trails
- Session-based audit logging with retention policy
- REST API (FastAPI): upload, suggest, audit report, session management
- File-based session isolation with TTL cleanup
- 280+ passing tests

**What was built (Shape):**

- Suggestion engine (LLM-based question rewording)
- Validation engine (deterministic rule checks + LLM-assisted analysis)
- Auto-tagging engine with session vocabulary awareness
- Style profile system (language, preferences, institutional style guide)
- Platform adapters: LimeSurvey, Qualtrics, SurveyMonkey, QTI
- Stateless REST API: `/import`, `/export`, `/create`, `/suggest`, `/validate`, `/tag`
- Stateful conversational API: `/chat/*` (session-scoped iterative authoring)
- Pilot UIs (HTMX-based) for both Shape and Cue
- 89 new tests (no regressions)

**Remaining for WP2:** None — all deliverables complete.

---

### WP3: Application Integration and Security, Privacy, and Compliance

**Period:** Apr – May · **Lead:** PXL

Integrate SDKs into PXL's existing survey platform. Map identity/tenancy. Configure inference providers (local/EU-hosted or third-party LLMs). Enable consent capture. Implement data minimisation and policy-based routing.

| Deliverable | Description                                                   | Status         |
|-------------|---------------------------------------------------------------|----------------|
| D3.1        | Integration package (backend hooks, UI widgets, configs)       | ⏳ Nearly complete |
| D3.2        | Provider configuration and fallbacks (local/EU-hosted/3rd party) | ✅ Complete — configurable via `LLM_BASE_URL` + per-use-case model overrides; provider options documented in `docs/OPERATOR_RUNBOOK.md` |
| D3.3        | Operator runbook and observability dashboards (audit/metrics)   | ⏳ Partially done — runbook in `docs/OPERATOR_RUNBOOK.md`; observability dashboards pending |

**Already completed (early):**

- OIDC authentication with Keycloak (bundled in docker-compose)
- JWT-based session middleware
- Security event logging
- Docker Compose setup with both services + Keycloak
- Consent capture at session start
- Tenant/session isolation

**Remaining for WP3:**

- Integration into PXL's existing survey platform (Mosquito) — nearly complete
- Provider fallback configuration (EU-hosted/local model support)
- Operator runbook — ✅ complete (`docs/OPERATOR_RUNBOOK.md`)
- Observability dashboards (MLFlow) — pending
- Pilot onboarding (PXL internal + partner institution) — underway

---

### WP4: Evaluation, Dissemination, and Online Showcase

**Period:** May – Jun · **Lead:** PXL

Execute pilot measurements and analysis. Produce interim and final evaluation inputs. Publish the online showcase. Deliver TNC presentation/demo.

| Deliverable | Description              | Status   |
|-------------|--------------------------|----------|
| D4.1        | Online showcase           | Upcoming |
| D4.2        | TNC presentation/demo     | Upcoming |

**Planned activities:**

- Pilot user testing with administrators and respondents
- Collect metrics: authoring time, response time, citation accuracy, acceptance/edit rates
- Bug fixes from pilot feedback
- Final evaluation report
- Online showcase (architecture, deployment recipes, demo video, results)
- Live demo at GÉANT TNC25
- Open-source release under restricted licence (PolyForm Noncommercial 1.0.0)
- Final report (due 31 July 2026)

---

## 5. Communications

**Internal coordination:** The team (3 members, same institution) coordinates via weekly stand-ups and a shared task board. Technical decisions are tracked in OpenSpec change proposals (`openspec/changes/`); completed work is archived with full audit trail.

**GÉANT reporting:** Progress updates are shared with the GIP programme office at milestone completions and upon request. This project plan serves as the living status document.

**Pilot partners:** Onboarding communication with pilot participants (PXL internal and partner institution) is handled directly by the project lead. Participants receive an information sheet covering scope, data handling, and consent before joining.

**Public dissemination:** Results will be presented at GÉANT TNC25 (11 June 2026) via a live demo and presentation. An online showcase with architecture documentation, deployment recipes, and pilot results will be published after the conference.

---

## 6. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Pilot users unavailable or delayed | Medium | High | Pre-arranged with PXL staff; pilot UIs enable standalone testing without full platform integration |
| LLM API cost overruns during pilot | Low | Medium | Per-use-case model configuration allows cheaper models for high-volume tasks (e.g. query rewriting); token usage monitored via OpenRouter dashboard |
| External LLM provider outage | Low | Medium | Architecture supports any OpenAI-compatible endpoint; operator can switch provider via env var without code changes |
| Insufficient retrieval quality for pilot | Medium | Medium | Query rewriting improves retrieval; citation distance threshold is configurable; iterative tuning possible during pilot |
| Integration delays with PXL survey platform | Low | High | Pilot UIs provide a standalone fallback for evaluation if full integration is delayed |

---

## 7. Course Adjustments

Deviations from the original application form, reflecting decisions made during implementation:

### Scope adjustments

- **Audio/video document support deferred.** The original plan mentioned text, audio, video, and URL artefacts for Cue. The PoC focuses on text-based documents (PDF, DOCX, TXT, Markdown). Audio/video transcription is a post-pilot candidate.
- **No PostgreSQL database.** Audit reports and session data use file-based storage (per-session directories). This simplifies deployment and reinforces session isolation. PostgreSQL remains a future option.
- **Local LLM support deferred.** The pilot uses OpenRouter as the primary LLM provider. On-premise LLM support (Ollama, LM Studio) is out of scope for the PoC but the architecture supports it.

### Additions beyond original scope

- **Platform adapters for survey creation.** Shape gained write-back capability to LimeSurvey (RC2 API), Qualtrics (v3 API), SurveyMonkey, and QTI — enabling direct survey creation and export across multiple platforms.
- **Stateful conversational API.** Shape includes a session-scoped `/chat/*` API where an LLM orchestrates internal tool calls (suggest, validate, tag) server-side, enabling iterative questionnaire authoring through natural conversation.
- **Pilot UIs.** HTMX-based web interfaces were built for both Shape (chat + survey preview + export) and Cue (survey UI for respondents), enabling pilot testing without requiring integration into PXL's existing platform first.

### Timeline changes

- **WP2 completed ahead of schedule.** Both SDKs reached functional completeness by mid-March (6 weeks ahead of the end-April target). This provides buffer for WP3 integration work.
- **OIDC/Keycloak implemented early.** Authentication and identity management (originally part of WP3) was completed during WP2, integrated directly into the SDK architecture.

---

## 8. Forward Plan (March – June 2026)

### March – April: WP3 focus

- [x] Complete remaining Cue API tests and archive change
- [x] Developer documentation for Cue and Shape SDKs
- [x] Operator runbook (`docs/OPERATOR_RUNBOOK.md`)
- [x] Query rewriting for improved RAG retrieval quality
- [ ] Integration into PXL's survey platform — nearly complete
- [ ] Provider fallback configuration
- [ ] Pilot onboarding (PXL internal + partner institution) — underway

### May: Pilot & WP4 kickoff

- [ ] Pilot execution with real users
- [ ] Metrics collection and interim analysis
- [ ] Bug fixes from pilot feedback
- [ ] TNC abstract submission and preparation
- [ ] Online showcase content preparation

### June: Dissemination & Close-out

- [ ] Final pilot analysis and evaluation report
- [ ] TNC25 live demo and presentation
- [ ] Online showcase publication
- [ ] Open-source release preparation
- [ ] Final report (due 31 July 2026)

---

