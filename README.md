# Expats (GÉANT): Explainable Autofill for Trustworthy Surveys

A platform providing two AI co-pilots that improve questionnaire quality and response completeness while prioritizing privacy, transparency, and user control.
All code is open-source for non-commercial use only.

## Overview

**Expat-GÉANT** is a proof-of-concept developed by PXL University College to build and evaluate privacy-first, standalone AI modules for the European research and education community.

### Core Components

- **M-Chat**: Administrator co-pilot for questionnaire design — accelerates creation with guardrails, consistency checks, tagging, and summarization
- **M-Autofill**: Respondent assistant for evidence - based answer suggestions—retrieves relevant passages from user documents, proposes concise answers with citations, and explains reasoning
- **M-Shared**: Common utilities and foundational infrastructure for both modules

## Key Features

✨ **Privacy by Default**

- Session-based data isolation with automatic TTL-based cleanup
- No user profiling or cross-session tracking
- GDPR-aligned governance with audit trails
- Optional local LLM support for fully on-premise deployments

🎯 **Interoperability**

- QTI 3.0-compatible questionnaire import/export
- SDK-first, embeddable API design for institutional reuse
- Designed for integration into existing survey platforms and educational tools

📊 **Evidence-Based**

- Citation system with precise source tracking (line numbers, timestamps, highlights)
- Transparent reasoning: understand where suggestions come from
- Quality metrics: citation accuracy, response completeness, edit/acceptance rates

## Project Structure

```
.
├── m_autofill/     # Respondent answer suggestion assistant
├── m_chat/         # Administrator questionnaire design assistant (planned)
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
- **Auth**: OAuth 2.0 & JWT

## Quick Start

### Prerequisites

- Docker & Docker Compose
- OpenRouter or OpenAI API key (or local LLM alternative)

### Installation

```bash
# Clone repository
git clone https://github.com/pxl-be/expat-geant.git
cd expat-geant

# Configure environment
cp .env.example .env
# Edit .env: set OPENROUTER_API_KEY (or OPENAI_API_KEY) and JWT_SECRET

# Build and run
docker-compose up --build
```

The API is available at `http://localhost:8001`. Interactive docs at `http://localhost:8001/docs`.

See [Deployment Guide](docs/DEPLOYMENT.md) for full configuration options, manual Docker setup, data persistence, and production security guidance.

## Documentation

- [Project Context](openspec/project.md) — Detailed specifications, tech stack, conventions, and constraints
- [Deployment Guide](docs/DEPLOYMENT.md) — Docker & local setup, environment variables, testing
- [Integration Guide](docs/INTEGRATION.md) — JWT/auth setup, institutional SSO, API endpoint reference
- [Data Model](docs/DATA_MODEL.md) — Internal data structures, Mermaid diagrams, platform mapping
- [Adapter Guide](docs/ADAPTERS.md) — Writing custom survey platform adapters
- [M-Autofill Module](m_autofill/README.md) — Answer suggestion assistant
- [M-Chat Module](m_chat/README.md) — Questionnaire design assistant *(planned)*
- [Shared Utilities](m_shared/README.md) — Common infrastructure

## Contributing

**Local Development**

```bash
# Clone repository
git clone https://github.com/pxl-be/expat-geant.git
cd expat-geant

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
# API available at: http://localhost:8001
# Docs available at: http://localhost:8001/docs
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

- **Pilot & evaluation**: Implement at PXL + Belnet partner; measure authoring time, respondent time, citation accuracy, acceptance/edit rates
- **Demo & dissemination**: Live demo at GÉANT TNC (May 2026); online showcase with architecture & results
- **Reusable outputs**: Containerized Docker images, REST APIs, SDK, deployment recipes, admin templates, evaluation scripts
- **Documentation**: Deployment guides, integration docs, style guides for institutional reuse
- **Timeline**: Jan–May 2026 (PoC), final report by 30 June 2026

## Contact & Support

Project lead: PXL University College (contact details TBD)  
Questions or contributions: See [Contributing](#contributing) section

---

**This is a proof-of-concept project. Simplicity, clarity, and maintainability are prioritized over completeness.**
