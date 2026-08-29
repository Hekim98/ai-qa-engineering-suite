# Roadmap

The roadmap deliberately validates a service before attempting a SaaS platform.

## Milestone 1 — Foundation (current)

- [x] Installable `src/` package structure
- [x] Architecture and quality documentation
- [x] Typed, validated YAML project configuration
- [x] Environment-based secret resolution and safe paths
- [x] Idempotent console/rotating-file logging
- [x] Unit tests, coverage threshold, lint, type-check, and CI baseline

Exit condition: a clean checkout can install dependencies, validate the example configuration, and pass framework tests.

## Milestone 2 — Browser automation core

- [ ] Playwright and Pytest integration
- [ ] Browser/context/page fixtures
- [ ] Screenshot, trace, and video capture
- [ ] Console and network error collection
- [ ] First reusable smoke-test pack

Exit condition: one command runs a documented smoke journey and preserves useful failure evidence.

## Milestone 3 — Sample audit

- [ ] Select a representative AI-built demo application
- [ ] Define client-specific critical flows
- [ ] Run automated and exploratory QA
- [ ] Record structured defects with evidence

Exit condition: verified findings are complete enough to support a client-quality report.

## Milestone 4 — Launch QA report

- [ ] Severity model
- [ ] Launch-readiness scoring model
- [ ] HTML/PDF report generation
- [ ] Portfolio-quality sample report

Exit condition: a founder can understand launch risk and recommended next actions without reading test code.

## Milestone 5 — Market validation

- [ ] Contact 20–30 well-matched founders
- [ ] Complete one pilot audit
- [ ] Collect outcome-focused feedback or a testimonial
- [ ] Secure the first paid engagement

Exit condition: payment validates the offer strongly enough to justify further investment.

## Later phases

API and workflow QA, AI-feature evaluation, AI-agent reliability evaluation, continuous release QA, and only then a potential product/dashboard layer.
