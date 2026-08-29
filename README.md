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

Milestone 3 completes the first portfolio audit against SauceDemo: full Chromium desktop coverage, Chromium mobile and Firefox/WebKit smoke coverage, verified findings, a manual exploratory checklist, and a separate seeded-defect Detection Demonstration.

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
audits/                  Verified findings and exploratory audit records
docs/                    Architecture, roadmap, and quality standards
tests/                   Framework tests and client-specific audit suites
artifacts/runs/          Generated run evidence (not committed)
output/                  Final HTML/PDF portfolio deliverables
```

## Local setup

Python 3.11 or newer is recommended.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m playwright install chromium firefox webkit
cp .env.example .env
pytest
```

Load and inspect the example project configuration:

```bash
ai-qa validate configs/example.yaml
```

Run one configured browser profile:

```bash
ai-qa test configs/example.yaml --profile desktop-chromium
```

Each execution writes an ignored directory below `artifacts/runs/` containing logs, browser evidence, observability records, and a machine-readable `run.json`.

## SauceDemo portfolio audit

SauceDemo publishes its test personas on the login page. Configure the standard readiness persona locally:

```bash
export SAUCEDEMO_USERNAME=standard_user
export SAUCEDEMO_PASSWORD=secret_sauce
ai-qa validate configs/saucedemo.yaml
ai-qa test configs/saucedemo.yaml
```

The standard-user readiness suite and intentionally faulty `problem_user` profile are separate. Detection Demonstration findings never affect readiness scoring.

Verified audit inputs are stored in [audits/saucedemo](audits/saucedemo). Public-site CI is defined only as a manually started GitHub Actions workflow, so normal pushes never send traffic to SauceDemo.

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
