# Architecture

## Goal

The suite separates reusable quality-engineering capabilities from client-specific business logic. A new engagement should normally require a project configuration, selected reusable test packs, custom critical flows, and human exploratory testing—not a rewritten framework.

## Layers

### 1. Core QA engine

Owns typed configuration, secret resolution, safe paths, fixtures, browser lifecycle, assertions, logging, evidence capture, and network/console monitoring. Browser profiles run in isolated Pytest subprocesses so one failed browser cannot contaminate another profile.

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

An unreachable environment or HTTP 5xx during guarded navigation marks the run `incomplete`; it is not silently converted into a product defect.

## Configuration boundary

`configs/example.yaml` documents the first public configuration contract. Pydantic rejects unknown or invalid input before any test run starts. Configuration stores only the names of credential environment variables; their values come from the process environment or an ignored local `.env` file.

## Portfolio audit boundary

`configs/saucedemo.yaml` and `tests/saucedemo/` form the first client layer. Full readiness uses `standard_user`; the intentionally faulty `problem_user` is selected only by a dedicated `detection_demo` profile. Source classification keeps seeded demonstration findings out of readiness scoring.

The external-site workflow uses `workflow_dispatch` only. Push and pull-request quality checks run local fixtures and framework tests without contacting SauceDemo.

## Report data contract

Every finding carries:

- stable ID and title;
- severity and affected environment;
- reproduction steps;
- expected and actual results;
- evidence paths and relevant logs;
- recommendation and verification status.

The report command validates `run.json`, structured findings, and every referenced evidence path before rendering. A single immutable `LaunchReport` model drives both HTML and PDF outputs, preventing scoring or content drift between formats. Seeded `detection-demonstration` findings remain visible in a separate appendix but are excluded from readiness scoring.

Category assessments use PASS=1, WARNING=0.5, and FAIL=0 against weights of 40, 20, 15, 10, 10, and 5. A blocked required assessment suppresses the score and produces an `INCOMPLETE` recommendation. Critical findings or failed critical flows always produce `DO NOT LAUNCH`.
