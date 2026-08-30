# QA Practice Client Simulation

## Purpose

This second client pack demonstrates how the reusable engine is adapted to a new web product without changing browser execution, evidence retention, observability, scoring, or report rendering.

The target is the QA Practice e-commerce page, a public automation sandbox with a realistic catalog, cart, address, payment, and order-confirmation journey. The provider publishes stable locators, expected test cases, dummy payment data, and states that practice input is not stored.

## Client handoff received

- Target and environment: recorded in `audits/qapractice/client-intake.yaml`.
- Authorized scope and excluded actions: recorded in the same intake file.
- Critical flows and browser matrix: `configs/qapractice.yaml`.
- Test data: non-persistent dummy shopper, address, and payment values from the public guide.
- Acceptance criteria: published test cases plus the suite's standard launch-readiness rules.

No credentials are required. This engagement exposed and resolved a reusable-engine assumption: project credentials are now optional and requested only by tests that need them.

## Files added for this client

```text
configs/qapractice.yaml
tests/qapractice/
audits/qapractice/client-intake.yaml
audits/qapractice/manual-exploratory-checklist.yaml
```

The reusable `src/ai_qa_engineering/` engine remains client-independent.

## Safe execution

Validate the client contract:

```bash
ai-qa validate configs/qapractice.yaml
```

Run one learning profile first:

```bash
ai-qa test configs/qapractice.yaml --profile desktop-chromium
```

After inspecting `run.json`, screenshots, traces, console records, and network records, run the full configured matrix:

```bash
ai-qa test configs/qapractice.yaml
```

The test pack does not submit contact forms, create accounts, perform real payments, run load tests, or probe security. The checkout uses only the sandbox's published dummy values.

## Verified audit result

**60/100 — DO NOT LAUNCH** for the declared Chromium, Firefox, and WebKit scope.

- Chromium desktop: 8 passed, 1 semantic accessibility failure.
- Chromium mobile at 390x844: 3 critical smoke checks passed.
- Firefox desktop: catalog and responsive smoke passed; checkout failed.
- WebKit desktop: catalog and responsive smoke passed; checkout failed.
- Verified findings: 1 Major cross-browser checkout defect and 1 Minor missing-main-landmark defect.
- Unexpected first-party console/network failures: none in the verified runs.

The critical checkout flow succeeds in Chromium desktop/mobile, but Firefox and WebKit discard every shipping-address value and never expose payment. The same behavior was reproduced with standard Playwright fill actions and sequential keyboard input. The score is published, but the failed critical flow independently forces the `DO NOT LAUNCH` decision.

Deliverables:

- `audits/qapractice/manual-findings.yaml`
- `audits/qapractice/verified-audit.yaml`
- `output/html/qa-practice-store-launch-readiness-report.html`
- `output/pdf/qa-practice-store-launch-readiness-report.pdf`

## Learning path

1. Read `client-intake.yaml` to understand what the customer supplied and authorized.
2. Read `qapractice.yaml` to see how business scope becomes executable configuration.
3. Read `tests/qapractice/support.py` to see the product-specific vocabulary.
4. Read the three test modules to see expected behavior expressed as checks.
5. Run one profile and inspect its immutable artifact directory.
6. Reproduce any failure manually before converting it into a verified finding.
7. Complete the exploratory checklist and only then generate a readiness report.

## Current boundary

Automated failures are evidence, not automatically approved product findings. A human still verifies severity, expected behavior, reproducibility, and launch impact. Multi-profile results are currently consolidated into the final findings document by the auditor rather than automatically merged by the report command.
