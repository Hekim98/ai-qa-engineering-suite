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

Milestone 8 completes the verified report workspace inside AI QA Control Room. Human-reviewed
findings, category assessments, and critical-flow results now produce one deterministic score and
matching HTML/PDF reports with automated and human visual verification.

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

Run a complete, combined audit with one retry for failed profiles:

```bash
ai-qa audit configs/qapractice.yaml
```

The orchestrator creates one immutable package below `artifacts/audits/`, combines the browser
matrix, separates persistent failures from flaky tests, builds an evidence index, and renders
unscored draft HTML/PDF summaries. See [Audit Orchestrator v1](docs/AUDIT_ORCHESTRATOR.md).

Generate both report formats from a completed run and verified findings:

```bash
ai-qa report artifacts/runs/<run-id> --findings audits/saucedemo/manual-findings.yaml
```

Each execution writes an ignored directory below `artifacts/runs/` containing logs, browser evidence, observability records, and a machine-readable `run.json`.

The generic **Manual customer audit** GitHub Actions workflow can run a selected config without
Codex or a local installation. It is manual-only, so pushes never contact configured targets.

## Local audit dashboard

Start the private local interface:

```bash
ai-qa dashboard
```

Choose a configuration and browser profiles, start one background audit, inspect its profile
attempts and evidence, then confirm or reject every automated candidate. Review decisions survive
dashboard restarts in the ignored audit package. The report-preparation gate never opens for an
incomplete audit or while a candidate is undecided.

Complete all six category assessments and every configured critical flow, save limitations and
the executive summary, then generate the final report. The dashboard checks HTML identity, PDF
structure and text, runs `pdfinfo`, renders every PDF page to PNG with Poppler, and requires a
human visual approval before the report is marked verified. See
[Verified Report Workspace](docs/VERIFIED_REPORT_WORKSPACE.md).

## Controlled authenticated audit

The authentication sandbox provides a safe end-to-end example with fixed synthetic member,
administrator, and locked accounts:

```bash
cp .env.example .env
ai-qa audit configs/auth-sandbox.yaml
```

It runs the complete authenticated suite in desktop Chromium and critical smoke journeys in
mobile Chromium, Firefox, and WebKit. Browser session state is held in an auto-deleted private
temporary directory and never enters audit artifacts. See
[Authenticated Journeys](docs/AUTHENTICATED_JOURNEYS.md).

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
