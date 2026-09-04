# Verified Report Workspace

## Purpose

The report workspace completes an audit without requiring a separate YAML-authoring step. It
preserves human judgment as structured data, applies deterministic scoring, generates matching
HTML and PDF outputs, and records both automated verification and final visual approval.

## Complete an audit

1. Open a completed audit in AI QA Control Room.
2. Confirm or reject every automated candidate. Confirmed candidates require severity, category,
   reproduction steps, expected and actual behavior, recommendation, and retained evidence.
3. Enter an executive summary.
4. Assess all six score categories with `PASS`, `WARNING`, `FAIL`, or `BLOCKED` and an
   evidence-based rationale.
5. Assess every critical flow captured by the audit and describe the supporting evidence.
6. Record at least one limitation and any harmless allowlisted network or console observations.
7. Save the workspace and generate the report.
8. Open every rendered PDF page, inspect it, and record a visual-review note.

The visual check must cover clipping, overflow, broken tables, unreadable text, blank pages,
incorrect page order, and evidence images that are too small to interpret.

## Scoring and recommendation

The existing fixed weights remain authoritative:

| Category | Weight |
| --- | ---: |
| Core flows | 40 |
| Reliability and error handling | 20 |
| UX and content | 15 |
| Responsive behavior | 10 |
| Accessibility smoke | 10 |
| Network health | 5 |

`PASS` earns the full category weight, `WARNING` earns half, and `FAIL` earns zero. A blocked
required assessment suppresses the score. Critical findings or failed critical flows force `DO
NOT LAUNCH`; a score below 70 also blocks launch. Scores from 70 through 89, or any Major finding,
produce `LAUNCH WITH CONDITIONS`. A score of at least 90 with no Critical or Major findings and
all critical flows passing produces `READY TO LAUNCH`.

## Generated audit records

The ignored audit directory contains the complete review trail:

```text
report-workspace.json
verified-report-inputs.yaml
verified-launch-report.json
report-verification.json
reports/launch-readiness-report.html
reports/launch-readiness-report.pdf
report-verification/pages/page-1.png
```

Additional rendered pages use sequential filenames. The verification record stores the exact
input digest, automated checks, score, recommendation, report paths, and visual-review approval.
Changing a confirmed finding or workspace assessment changes the digest and marks the old output
stale until it is generated and inspected again.

## Automated report checks

Before the PDF is available for approval, the suite requires:

- a complete HTML document with the verified title and recommendation;
- a parseable, unencrypted PDF with text on every page;
- matching title and recommendation text in the PDF;
- a `pdfinfo` page count equal to the parsed document;
- one valid, non-blank portrait PNG from Poppler for every PDF page.

Poppler must provide `pdfinfo` and `pdftoppm` on the local machine. A missing dependency produces
an actionable error and no report can be visually approved.

## Trust boundary

Workspace data is stored only inside the selected ignored audit package. State-changing requests
use the dashboard's local token. Evidence must remain inside the audit directory, and report files
and rendered pages are served only through the existing allowlist. A candidate decision, score, or
visual approval is never inferred by an LLM.
