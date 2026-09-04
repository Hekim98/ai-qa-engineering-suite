# Roadmap

The roadmap deliberately validates a service before attempting a SaaS platform.

## Milestone 1 — Foundation

- [x] Installable `src/` package structure
- [x] Architecture and quality documentation
- [x] Typed, validated YAML project configuration
- [x] Environment-based secret resolution and safe paths
- [x] Idempotent console/rotating-file logging
- [x] Unit tests, coverage threshold, lint, type-check, and CI baseline

Exit condition: a clean checkout can install dependencies, validate the example configuration, and pass framework tests.

## Milestone 2 — Browser automation core

- [x] Playwright and Pytest integration
- [x] Browser-profile execution and isolated run directories
- [x] Screenshot, trace, and video evidence policies
- [x] Console and network error collection
- [x] Structured `run.json` output and incomplete-run classification
- [x] First reusable page-health smoke pack

Exit condition: one command runs a documented smoke journey and preserves useful failure evidence.

## Milestone 3 — Sample audit

- [x] Select SauceDemo as the stable public portfolio target
- [x] Define authentication, catalog, cart, checkout, and session critical flows
- [x] Run Chromium desktop/mobile and Firefox/WebKit audit profiles
- [x] Complete responsive, keyboard, error-message, UX, and edge-case checks
- [x] Record verified readiness findings with failure evidence
- [x] Isolate the `problem_user` Detection Demonstration from readiness

Exit condition: verified findings are complete enough to support a client-quality report.

## Milestone 4 — Launch QA report

- [x] Severity model
- [x] Launch-readiness scoring model
- [x] HTML/PDF report generation
- [x] Portfolio-quality sample report

Exit condition: a founder can understand launch risk and recommended next actions without reading test code.

## Milestone 5 — Audit Orchestrator

- [x] Run the selected browser matrix with one command
- [x] Group profile runs below one immutable audit ID
- [x] Retry failures once and separate persistent failures from flaky tests
- [x] Generate an evidence index and candidate-finding review queue
- [x] Render explicitly unscored draft HTML/PDF reports
- [x] Add secret preflight, named test accounts, redaction, and visual masking support
- [x] Add a generic manual-only GitHub Actions audit workflow

Exit condition: one command creates a complete multi-browser review package without publishing
unverified findings, scores, or recommendations.

## Milestone 6 — Authenticated journeys and role coverage

- [ ] Add reusable login/session-state helpers
- [ ] Exercise default and named accounts in one controlled audit
- [ ] Verify role boundaries, logout, expiration, and recovery paths
- [ ] Demonstrate the capability against an authorized sandbox target

## Milestone 7 — Local audit dashboard

- [ ] Start audits without terminal commands
- [ ] Review profile status, evidence, candidate findings, and flaky tests
- [ ] Confirm or reject findings before final report generation

## Deferred market validation

Founder outreach, pilot recruitment, and paid engagements remain intentionally deferred until the
technical workflow is ready for the desired level of independent use.

## Later phases

AI-assisted finding analysis, API and workflow QA, AI-feature evaluation, AI-agent reliability
evaluation, continuous release QA, and later a potential hosted product layer.
