# Contributing

Thanks for your interest in Expats. This document explains how you can engage
with the project during the proof-of-concept phase (January–June 2026, funded
by the GÉANT Innovation Programme).

## How You Can Contribute

### Reporting Issues

Bug reports, documentation improvements, and feature ideas are very welcome.
Please file them as **GitHub issues** at
<https://github.com/pxl-research/expats-geant/issues>.

A good issue includes:

- What you tried and what happened
- What you expected to happen
- Affected component (`cue_api`, `cue_ui`, `shape_api`, `shape_ui`, `m_shared`)
- Steps to reproduce, with versions / commit SHA where possible

For **security-sensitive issues**, please follow [`SECURITY.md`](SECURITY.md)
instead of filing a public issue.

For **privacy / data-protection issues**, see [`PRIVACY.md`](PRIVACY.md).

### Pull Requests

External pull requests are **not accepted** during the PoC phase. The project
is delivered by a small grant-funded team with a fixed scope and timeline; we
do not have the capacity to maintain a public review and contribution pipeline
before the GÉANT TNC dissemination milestone (May 2026).

If you have a change you would like to see merged:

1. File an issue describing the problem and your proposed approach
2. We will respond, discuss, and — where it fits the scope — pick the work up
   internally
3. After the PoC phase, the contribution model will be revisited

This restriction does not apply to PXL University College team members and
named project partners; they follow the [Git Workflow](openspec/project.md#git-workflow).

### Institutional Reuse and Integration

If you represent an institution (NREN, university, research organisation) and
want to:

- Pilot or deploy Expats internally
- Integrate Expats components into an existing survey platform
- Discuss adaptations, extensions, or commercial licensing (the codebase is
  under the [PolyForm Noncommercial License 1.0.0](LICENSE) for the PoC)

please contact:

**Servaas Tilkin** — PXL University College
Email: <servaas.tilkin@pxl.be>

## Local Development

See the [Local Development section in the README](README.md#contributing) for
setup. Briefly:

```bash
git clone https://github.com/pxl-research/expats-geant.git
cd expats-geant
python3 -m venv .venv
source .venv/bin/activate
pip3 install -r requirements.txt
cp .env.example .env  # edit and add your API keys
```

Documentation for individual components:

- [Cue API](docs/CUE_API.md), [Shape API](docs/SHAPE_API.md),
  [Adapters](docs/ADAPTERS.md), [Deployment](docs/DEPLOYMENT.md),
  [Testing](docs/TESTING.md), [Operator Runbook](docs/OPERATOR_RUNBOOK.md)

## Coding Conventions

- PEP 8 + the project's pre-commit hooks (`ruff`, `mypy`)
- Type hints everywhere; tests for behavioural changes
- Commit message prefixes: `FEAT:`, `FIX:`, `CHANGE:`, `DOCS:`, `TEST:`,
  `REFACTOR:`, `CHORE:`
- See [`openspec/project.md`](openspec/project.md) and
  [`openspec/AGENTS.md`](openspec/AGENTS.md) for the spec-driven workflow and
  detailed conventions

The guiding principle for the codebase is: **clean, simple, maintainable —
prefer the approach with fewer moving parts**.

## Code of Conduct

The project follows GÉANT community norms: be respectful, constructive, and
inclusive. Harassment or abusive behaviour will not be tolerated. To raise a
concern, contact <servaas.tilkin@pxl.be>.
