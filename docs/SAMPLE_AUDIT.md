# Verified SauceDemo Sample Audit

## Launch decision

**80/100 — LAUNCH WITH CONDITIONS**

Standard-user authentication, catalog, cart, checkout, session, and cross-browser smoke flows completed successfully. Launch should proceed only after addressing the keyboard-inaccessible cart control, with semantic, mobile-spacing, and route-response defects tracked as follow-up conditions.

The decision is based only on standard-user behavior. The intentionally faulty `problem_user` result is documented in a separate Detection Demonstration and does not affect the readiness score.

## Score breakdown

| Category | Weight | Status | Earned |
| --- | ---: | --- | ---: |
| Core flows | 40 | PASS | 40 |
| Reliability and error handling | 20 | PASS | 20 |
| UX and content | 15 | PASS | 15 |
| Responsive | 10 | WARNING | 5 |
| Accessibility smoke | 10 | FAIL | 0 |
| Network health | 5 | FAIL | 0 |
| **Total** | **100** |  | **80** |

## Verified readiness findings

| ID | Severity | Finding |
| --- | --- | --- |
| SD-A11Y-002 | Major | Cart link cannot receive keyboard focus |
| SD-A11Y-001 | Minor | Inventory lacks primary semantic landmarks |
| SD-NET-001 | Minor | Reloading inventory returns HTTP 404 |
| SD-RESP-001 | Minor | Mobile product cards contain excessive vertical whitespace |

The Detection Demonstration separately confirms that the suite identifies the `problem_user` persona's repeated incorrect product image.

## Coverage

- Chromium desktop: full suite, 10 passed and 3 evidence-backed failures
- Chromium mobile at 390×844: critical smoke and responsive checks
- Firefox desktop: purchase smoke
- WebKit desktop: purchase smoke
- Manual UX, keyboard, error-message, and edge-case checklist

## Deliverables

- [Self-contained HTML report](../output/html/saucedemo-launch-readiness-report.html)
- [A4 PDF report](../output/pdf/saucedemo-launch-readiness-report.pdf)
- [Structured verified findings](../audits/saucedemo/manual-findings.yaml)

Both report formats were generated from the same validated data model. Automated tests verify report content and PDF text structure. The final seven-page PDF was also rendered to PNG with Poppler and every page was visually inspected for overflow, clipping, broken tables, and unreadable content.

## Limitations

This audit covers the public demo environment and its published test personas. Accessibility coverage is a semantic and keyboard smoke assessment, not a WCAG conformance audit. Security, load, backend API, payment integration, and assistive-technology testing are outside scope.
