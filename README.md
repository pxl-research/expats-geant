# Expats (GÉANT): Explainable Autofill for Trustworthy Surveys

A platform providing two AI co-pilots that improve questionnaire quality and response completeness while prioritizing privacy, transparency, and user control.
All code is open-source for non-commercial use.

## Overview

**Expats** is a prototype developed by PXL University College to build and evaluate privacy-first, standalone AI modules for the European research and education community.

### Core Components

- **Shape**: an administrator co-pilot for questionnaire design — accelerates creation with guardrails, consistency checks, tagging, and summarization
- **Shape UI**: a browser-based authoring frontend for Shape — server-rendered FastAPI app (Jinja2 + HTMX) for drafting surveys conversationally, previewing them live, and exporting to platform formats
- **Cue**: a respondent assistant for evidence-based answer suggestions — retrieves relevant passages from user documents, proposes concise answers with citations, and explains reasoning
- **Cue UI**: a browser-based survey review frontend — server-rendered FastAPI app (Jinja2 + HTMX) for uploading surveys, reviewing AI suggestions, and submitting responses without custom integration work
- **M-Shared**: common utilities and foundational infrastructure for both modules

## Key Features

✨ **Privacy by Default**

- Session-based data isolation with automatic TTL-based cleanup
- No user profiling or cross-session tracking
- GDPR-aligned governance with audit trails
- Optional local LLM support for fully on-premise deployments

🎯 **Interoperability**

- Designed for integration into existing survey platforms and educational tools
- SDK-first, embeddable API design for institutional reuse
- Bidirectional import/export for QTI 3.0, LimeSurvey, Qualtrics, and SurveyMonkey

📊 **Evidence-Based**

- Citation system with source tracking (line numbers, timestamps, highlights)
- Transparent reasoning: understand where suggestions come from
- Quality metrics: citation accuracy, response completeness, edit/acceptance rates
- Multiple source modes: file upload (documents and images), pasted text, and (optional) URL ingestion with preview-before-store

## Project Structure

```
.
├── cue_api/        # Respondent answer suggestion assistant (REST API, port 8801)
├── cue_ui/         # Survey review frontend (Jinja2 + HTMX, port 8811)
├── shape_api/      # Administrator questionnaire design assistant (REST API, port 8802)
├── shape_ui/       # Authoring frontend for Shape (Jinja2 + HTMX, port 8812)
├── m_shared/       # Common utilities (LLM clients, vector DB, data models, auth)
├── tests/          # All tests (pytest)
├── docs/           # Deployment, integration, and API reference guides
├── demo_code/      # Standalone demos and prototypes
├── openspec/       # Project specifications and change proposals
└── README.md       # This file
```

## Tech Stack

- **Backend**: Python with FastAPI
- **Vector DB**: ChromaDB (semantic search & RAG)
- **LLM**: OpenRouter (primary) + OpenAI-compatible fallback + local LLM support
- **Deployment**: Docker & Docker Compose
- **Database**: PostgreSQL (future phase)
- **Auth**: OIDC & JWT

## Quick Start

### Prerequisites

- Docker & Docker Compose
- An OpenAI-compatible LLM API key — OpenRouter recommended; local LLMs (Ollama, vLLM, LM Studio) also supported

### Installation

```bash
# Clone repository
git clone https://github.com/pxl-research/expats-geant.git
cd expats-geant

# Configure environment
cp .env.example .env
# Edit .env: set OPENROUTER_API_KEY (or any OpenAI-compatible key) and JWT_SECRET
# For multi-tenant deployments (per-subsidiary LLM keys), see docs/DEPLOYMENT.md § Multi-Tenant Setup

# Build and run
docker-compose up --build
```

The Cue API is available at `http://localhost:8801` (interactive docs at `/docs`).
The Cue UI survey review frontend is available at `http://localhost:8811`.
The Shape API is available at `http://localhost:8802` (interactive docs at `/docs`).
The Shape UI is available at `http://localhost:8812`.

See [Deployment Guide](docs/DEPLOYMENT.md) for full configuration options, manual Docker setup, data persistence, and production security guidance.

## Documentation

- [Project Context](openspec/project.md) — Detailed specifications, tech stack, conventions, and constraints
- [Deployment Guide](docs/DEPLOYMENT.md) — Docker & local setup, environment variables, testing
- [Operator Runbook](docs/OPERATOR_RUNBOOK.md) — Operator decisions, GDPR checklist, onboarding
- [Cue API](docs/CUE_API.md) — JWT/auth setup, institutional SSO, Cue endpoint reference
- [Shape API](docs/SHAPE_API.md) — Shape endpoint reference, conversational session API
- [Testing Guide](docs/TESTING.md) — Conformance test suite, coverage, smoke tests
- [Data Model](docs/DATA_MODEL.md) — Internal data structures, Mermaid diagrams, platform mapping
- [Adapter Guide](docs/ADAPTERS.md) — Writing custom survey platform adapters
- [Cue Module](cue_api/README.md) — Answer suggestion assistant
- [Shape Module](shape_api/README.md) — Questionnaire design assistant
- [Shared Utilities](m_shared/README.md) — Common infrastructure

### Governance

- [Contributing](CONTRIBUTING.md) — How to report issues and request institutional reuse
- [Security Policy](SECURITY.md) — Vulnerability reporting and security posture
- [Privacy Notice](PRIVACY.md) — GDPR rights, retention, third-party processors
- [Cryptography Inventory](docs/CRYPTO_INVENTORY.md) — Algorithms, libraries, and operator hardening notes

### Pilot Templates

- [Participant Information Sheet (template)](docs/PARTICIPANT_INFORMATION_SHEET_TEMPLATE.md) — Horizon Europe-based, for institutions running pilots
- [Informed Consent Form (template)](docs/INFORMED_CONSENT_TEMPLATE.md) — companion to the Participant Information Sheet
- [Style Guide (template)](docs/STYLE_GUIDE_TEMPLATE.md) — institutional style profile for Shape

## Contributing

**Local Development**

```bash
# Clone repository
git clone https://github.com/pxl-research/expats-geant.git
cd expats-geant

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip3 install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your API keys

# Run the API server
python3 run_api.py
# API available at: http://localhost:8801
# Docs available at: http://localhost:8801/docs
```

We follow standard Python conventions (PEP 8), PyCharm formatting, and commit message prefixes: `FEAT:`, `FIX:`, `CHANGE:`, `DOCS:`, `TEST:`, `REFACTOR:`, `CHORE:`.

See [Git Workflow](openspec/project.md#git-workflow) for branching and review process.



## License

This software is licensed under the **[PolyForm Noncommercial License 1.0.0](LICENSE)**.

### What This Means

✅ **You can:**

- Use, modify, and distribute this software for **non-commercial purposes**
- Deploy in educational institutions, research organizations, and public sector organizations
- Contribute improvements and reuse within the GÉANT community

❌ **You cannot:**

- Use this software for commercial purposes or generate commercial advantage without permission

### Commercial Use

Organizations interested in commercial use, deployment, or licensing should contact:

**Servaas Tilkin**  
PXL University College  
📧 servaas.tilkin@pxl.be

For inquiries regarding commercial licensing, integration partnerships, or deployment arrangements, please reach out to discuss your needs.

## Deliverables & Roadmap

- **Reusable outputs**: Containerized Docker images, REST APIs, SDK, deployment recipes, admin templates, evaluation scripts
- **Documentation**: Deployment guides, integration docs, style guides for institutional reuse
- **Pilot & evaluation**: Implement at PXL + Géant partner; measure authoring time, respondent time, citation accuracy, acceptance/edit rates
- **Demo & dissemination**: Live demo at GÉANT TNC (June 2026); online showcase with architecture & results
- **Timeline**: Jan–June 2026 (PoC)

## Contact & Support

- **Bug reports, feature requests, documentation issues:** file a [GitHub issue](https://github.com/pxl-research/expats-geant/issues). See [CONTRIBUTING.md](CONTRIBUTING.md) for details.
- **Security vulnerabilities:** follow [SECURITY.md](SECURITY.md) — do not file a public issue.
- **Privacy / GDPR enquiries:** see [PRIVACY.md](PRIVACY.md). For the PXL-hosted demo/pilot, contact <dpo@pxl.be>.
- **Institutional reuse, integration, commercial licensing:** Servaas Tilkin, PXL University College — <servaas.tilkin@pxl.be>.
