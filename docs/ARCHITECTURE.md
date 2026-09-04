# Architecture

## Goal

The suite separates reusable quality-engineering capabilities from client-specific business logic. A new engagement should normally require a project configuration, selected reusable test packs, custom critical flows, and human exploratory testing—not a rewritten framework.

## Layers

### 1. Core QA engine

Owns typed configuration, secret resolution, safe paths, fixtures, browser and HTTP lifecycles,
assertions, logging, evidence capture, and network/console monitoring. Browser profiles run in
isolated Pytest subprocesses so one failed browser cannot contaminate another profile.

### 2. Reusable test packs

Contains broadly applicable checks such as authentication, navigation, forms, sessions, responsive behavior, accessibility smoke checks, API failures, and permissions. Test packs remain opt-in because not every product shares the same behavior.

### 3. Client layer

Contains environment settings, critical journeys, roles, test-data references, and product-specific tests. Secrets are supplied through environment variables and never committed.

### 4. Human exploratory QA

Covers confusing experiences, business-logic mistakes, surprising edge cases, inconsistent state, and risks that automated checks cannot reliably judge.

### 5. Report engine

Transforms verified findings and evidence into severity-ranked defects, a launch-readiness score, and a launch recommendation.

## Dependency direction

```text
Client configuration and flows
            ↓
     Reusable test packs
            ↓
       Core QA engine
            ↓
 Evidence and structured results
            ↓
        Report engine
```

The core must not import client-specific code. Reports consume structured results rather than browser objects so that browser, API, workflow, and future agent evaluations can share the same reporting layer.

## Run lifecycle

`ai-qa test` validates the project configuration, creates an immutable run ID, and starts one Pytest process per selected browser profile. The engine's `qa_page` fixture creates a profile-sized page through Pytest Playwright's managed `new_context` factory, preserving official screenshot, trace, and video retention while applying the exact configured viewport. The AI QA plugin writes normalized diagnostics and a versioned `run.json` before the process exits.

`ai-qa audit` adds an orchestration boundary above those isolated runs. It creates one audit ID,
executes the selected matrix below that audit, retries failing profiles once, compares test
outcomes by node ID, and produces a combined `audit.json`, evidence index, candidate review
queue, and explicitly unverified draft reports. It never feeds candidate failures directly into
launch-readiness scoring.

Authenticated tests use a profile-aware browser-context factory. A session may be saved and
restored through `SessionStateStore`, but its storage-state file lives in an owner-only operating-
system temporary directory and is deleted at the end of the Pytest session. It never becomes an
artifact. Named accounts are resolved once from environment variables and exposed to tests by
logical role rather than secret value.

An unreachable environment or HTTP 5xx during guarded navigation marks the run `incomplete`; it is not silently converted into a product defect.

Configured API checks use same-origin absolute paths only and never follow redirects automatically.
Authentication values are resolved from environment-variable names, held in memory, and applied by
the client unless a negative test explicitly omits them. Each request can assert an expected status,
Pydantic response model, and latency budget. The evidence writer masks auth/cookie headers,
configured secret values, and sensitive JSON fields before atomically persisting request/response
summaries. A connection, DNS, or timeout failure raises `APIUnavailableError`, makes the profile and
audit incomplete, and never enters the product-finding queue.

## Local review interface

`ai-qa dashboard` adds a presentation layer over the same configuration and orchestration APIs.
It runs one audit at a time in a background thread, discovers completed immutable packages from
configured audit roots, and stores human review decisions beside the selected ignored package.
The dashboard does not invoke a second browser runner or modify automation results.

The HTTP service binds only to loopback. A random request token protects mutations; Host-header
validation, restrictive response headers, config discovery boundaries, and evidence allowlisting
reduce exposure to local browser attacks and path traversal. Captured HTML and structured logs are
served as inert text rather than executable same-origin content.

Candidate confirmation requires severity, category, steps, expected and actual behavior, and a
recommendation. Rejection requires a rationale. Incomplete audits and undecided candidates keep
the report-preparation gate closed.

The verified report workspace collects every weighted category and configured critical-flow
assessment, plus the executive summary, limitations, and allowlisted observations. Browser and
device coverage is derived from the immutable audit snapshot. Confirmed candidates are converted
to complete `Finding` records; rejected candidates never enter the report. The resulting
`FindingsDocument` is hashed, scored, and rendered through the same immutable `LaunchReport` used
by the CLI report path.

Generated HTML and PDF files are not immediately considered verified. Structural and identity
checks run first, `pdfinfo` confirms the PDF page count, and Poppler renders every page to PNG.
API contract coverage is derived from the immutable audit snapshot beside browser/device coverage,
so the dashboard and both final report formats show the same checked endpoints, status outcomes,
latency budgets, schemas, and evidence links. Report-page images are exposed through the same
evidence allowlist for human inspection. A final visual approval is stored beside the report. Any
material workspace or finding change produces a new input hash and marks the prior report stale
until regeneration.

## Configuration boundary

`configs/example.yaml` documents the first public configuration contract. Pydantic rejects unknown or invalid input before any test run starts. Configuration stores only the names of credential environment variables; their values come from the process environment or an ignored local `.env` file.

## Portfolio audit boundary

`configs/saucedemo.yaml` and `tests/saucedemo/` form the first client layer. Full readiness uses `standard_user`; the intentionally faulty `problem_user` is selected only by a dedicated `detection_demo` profile. Source classification keeps seeded demonstration findings out of readiness scoring.

The external-site workflow uses `workflow_dispatch` only. Push and pull-request quality checks run local fixtures and framework tests without contacting SauceDemo.

`configs/auth-sandbox.yaml` and `tests/auth_sandbox/` form the controlled authentication layer.
Playwright intercepts its reserved `.test` origin and serves deterministic in-browser pages, so
the multi-browser audit exercises sessions and role boundaries without external network access.

`configs/workflow-sandbox.yaml` and `tests/workflow_sandbox/` form the controlled API/workflow
layer. A real loopback HTTP server shares order state between authenticated API endpoints and a
browser interface. This proves API-to-browser and browser-to-API state transitions without customer
systems, external traffic, or production data.

## Report data contract

Every finding carries:

- stable ID and title;
- severity and affected environment;
- reproduction steps;
- expected and actual results;
- evidence paths and relevant logs;
- recommendation and verification status.

The report command validates `run.json`, structured findings, and every referenced evidence path before rendering. The dashboard constructs the same strict report inputs from persisted human decisions and validates all candidate evidence inside the selected audit package. A single immutable `LaunchReport` model drives both HTML and PDF outputs, preventing scoring or content drift between formats. Seeded `detection-demonstration` findings remain visible in a separate appendix but are excluded from readiness scoring.

Category assessments use PASS=1, WARNING=0.5, and FAIL=0 against weights of 40, 20, 15, 10, 10, and 5. A blocked required assessment suppresses the score and produces an `INCOMPLETE` recommendation. Critical findings or failed critical flows always produce `DO NOT LAUNCH`.
