# Architecture

## Goal

The suite separates reusable quality-engineering capabilities from client-specific business logic. A new engagement should normally require a project configuration, selected reusable test packs, custom critical flows, and human exploratory testing—not a rewritten framework.

## Layers

### 1. Core QA engine

Owns typed configuration, secret resolution, safe paths, fixtures, browser lifecycle, assertions, logging, evidence capture, network and console monitoring, and scoring. Milestone 1 includes the first four foundations; the browser-facing components arrive incrementally.

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

## Configuration boundary

`configs/example.yaml` documents the first public configuration contract. Pydantic rejects unknown or invalid input before any test run starts. Configuration stores only the names of credential environment variables; their values come from the process environment or an ignored local `.env` file.

## Planned result model

Every finding will eventually carry:

- stable ID and title;
- severity and affected environment;
- reproduction steps;
- expected and actual results;
- evidence paths and relevant logs;
- recommendation and verification status.
