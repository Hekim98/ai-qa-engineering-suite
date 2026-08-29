# AI QA Engineering Suite

> AI creates software faster. We make sure it actually works.

AI QA Engineering Suite is a reusable quality-engineering foundation for AI-built web applications, SaaS products, AI features, and—later—agentic workflows. It is designed to support a professional service that combines automated checks, human exploratory testing, and AI-assisted analysis.

## First offer

**24-Hour AI-Built App Launch QA** helps founders test an AI-built application before customers find the bugs.

The first client-facing deliverable will include:

- a launch-readiness score;
- Critical, Major, and Minor findings;
- reproduction steps and expected/actual results;
- screenshots, videos, and relevant logs;
- a clear launch recommendation.

## Current milestone

Milestone 1 establishes an installable Python package, typed project configuration, secret resolution, repository-safe paths, logging, and automated quality gates. Browser automation is intentionally deferred to Milestone 2 so each layer can be reviewed before the next one is added.

```text
Core QA Engine
    ↓
Reusable Test Packs
    ↓
Project Configuration + Client-Specific Flows
    ↓
Human Exploratory QA
    ↓
AI-Assisted Analysis
    ↓
Professional Launch Report
```

## Repository layout

```text
src/ai_qa_engineering/   Installable reusable QA package
configs/                 Example and shared configuration contracts
docs/                    Architecture, roadmap, and quality standards
tests/                   Automated tests for the package itself
artifacts/runs/          Generated run evidence (not committed)
output/                  Final HTML/PDF portfolio deliverables
```

## Local setup

Python 3.11 or newer is recommended.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
pytest
```

Load and inspect the example project configuration:

```bash
ai-qa validate configs/example.yaml
```

Run all local quality gates:

```bash
ruff check .
ruff format --check .
mypy
pytest
```

## Design principles

- Build the engine once; adapt configuration and critical flows per client.
- Keep client secrets out of version control.
- Treat automation as support for human judgment, not a replacement for it.
- Capture evidence for every material finding.
- Validate paid demand before building a large platform.

See [Architecture](docs/ARCHITECTURE.md), [Roadmap](docs/ROADMAP.md), and [Quality Standards](docs/QUALITY_STANDARDS.md).
