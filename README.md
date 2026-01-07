# Expat-GÉANT: Privacy-First AI-Assisted Survey Platform

An open-source platform providing two AI co-pilots that improve questionnaire quality and response completeness while prioritizing privacy, transparency, and user control.

## Overview

**Expat-GÉANT** is a six-month proof-of-concept (Jan–Jun 2026) developed by PXL University College to build and evaluate privacy-first, standalone AI modules for the European research and education community.

### Core Components

- **M-Chat**: Administrator co-pilot for questionnaire design—accelerates creation with guardrails, consistency checks, tagging, and summarization
- **M-Autofill**: Respondent assistant for evidence-based answer suggestions—retrieves relevant passages from user documents, proposes concise answers with citations, and explains reasoning
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
├── m_chat/         # Administrator questionnaire design assistant
├── m_shared/       # Common utilities (LLM clients, vector DB, data models)
├── openspec/       # Project specifications and guidelines
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

- Python 3.9+
- Docker & Docker Compose
- OpenRouter API key (or local LLM alternative)

### Installation

```bash
git clone https://github.com/pxl-be/expat-geant.git
cd expat-geant
pip install -r requirements.txt
docker-compose up
```

## Documentation

- [Project Context](openspec/project.md) — Detailed specifications, tech stack, conventions, and constraints
- [M-Chat Module](m_chat/README.md) — Questionnaire design assistant
- [M-Autofill Module](m_autofill/README.md) — Answer suggestion assistant
- [Shared Utilities](m_shared/README.md) — Common infrastructure

## Contributing

We follow standard Python conventions (PEP 8), PyCharm formatting, and commit message prefixes: `FEAT:`, `FIX:`, `CHANGE:`, `DOCS:`, `TEST:`, `REFACTOR:`, `CHORE:`.

See [Git Workflow](openspec/project.md#git-workflow) for branching and review process.

## License

To be determined; restricted open-source license planned for community reuse.

## Pilot & Evaluation

- **Pilot institutions**: PXL University College, Belnet-connected partners
- **Timeline**: Jan–Jun 2026
- **Demo**: GÉANT TNC conference (June 2026)
- **Metrics**: Time saved for authors/respondents, citation accuracy, response completeness, edit/acceptance rates

## Contact & Support

Project lead: PXL University College (contact details TBD)  
Questions or contributions: See [Contributing](#contributing) section

---

**This is a proof-of-concept project. Simplicity, clarity, and maintainability are prioritized over completeness.**
