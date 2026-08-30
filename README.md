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

Milestone 5 validates whether founders will pay for the service. The campaign uses a fixed-scope founding pilot, a public-source prospect list, measurable conversion thresholds, and an explicit approval gate before any external outreach.

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

Generate both report formats from a completed run and verified findings:

```bash
ai-qa report artifacts/runs/<run-id> --findings audits/saucedemo/manual-findings.yaml
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

Portfolio deliverables:

- [Verified sample audit summary](docs/SAMPLE_AUDIT.md)
- [Self-contained HTML report](output/html/saucedemo-launch-readiness-report.html)
- [Visually verified PDF report](output/pdf/saucedemo-launch-readiness-report.pdf)

Market-validation materials:

- [Pilot experiment and success criteria](docs/MARKET_VALIDATION.md)
- [Founder outreach messages](outreach/templates.md)
- [Public-source prospect tracker](outreach/prospects.csv)

Second-client learning pack:

- [QA Practice client simulation](docs/QA_PRACTICE_CLIENT_SIMULATION.md)
- [Simulated customer intake](audits/qapractice/client-intake.yaml)
- [Executable client configuration](configs/qapractice.yaml)
- [Manual exploratory checklist](audits/qapractice/manual-exploratory-checklist.yaml)
- [Verified HTML client-simulation report](output/html/qa-practice-store-launch-readiness-report.html)
- [Verified PDF client-simulation report](output/pdf/qa-practice-store-launch-readiness-report.pdf)

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
