# Local Audit Dashboard

## Purpose

AI QA Control Room is a local interface for starting configured audits, watching their progress,
reviewing browser coverage and retained evidence, and recording human decisions about automated
failure candidates. It uses the existing audit engine rather than introducing a second execution
path.

## Start it

From an activated project environment:

```bash
ai-qa dashboard
```

The dashboard opens at `http://127.0.0.1:8765/`. On macOS, `scripts/start-dashboard.command` can
also be opened directly from Finder after the project has been installed once.

Use a different local port or prevent automatic browser opening when needed:

```bash
ai-qa dashboard --port 9123
ai-qa dashboard --no-open
```

Keep the launcher window open while using the dashboard. Closing it stops the local service but
does not remove completed audit packages or review decisions.

## Working flow

```text
select configuration and profiles
  -> start one background audit
  -> watch completion status
  -> inspect profile attempts and evidence
  -> confirm or reject every candidate
  -> open the report-preparation gate
```

Only one audit runs at a time. This avoids competing browser processes and makes the current job
unambiguous. Completed audits are discovered from their existing `artifacts/audits/` packages,
so restarting the dashboard does not hide prior work.

## Human-review rules

An automated failure remains a candidate until a reviewer decides:

- **Reject:** provide a rationale explaining why it is expected, duplicated, environmental, or
  otherwise not a product finding.
- **Confirm:** provide rationale, severity, score category, reproduction steps, expected behavior,
  actual behavior, and a recommendation.

Decisions are written atomically to `review-decisions.json` inside the ignored audit directory.
The report-preparation gate remains blocked while any candidate is pending or the audit is
incomplete. A clean audit with no candidates opens the gate automatically.

Opening this gate does not invent category assessments, business impact, or a readiness score.
The existing verified report workflow still requires complete human-authored report inputs. A
later milestone can bring those final inputs and report generation into the same interface.

## Local security boundary

- The server binds only to `127.0.0.1`; it is not exposed to the local network.
- Requests with a non-local `Host` header are rejected to reduce DNS-rebinding risk.
- Every state-changing request requires a random token injected into the served page.
- Responses use a restrictive Content Security Policy, no caching, frame denial, and MIME
  sniffing protection.
- Configuration choices come only from validated YAML files directly below `configs/`.
- Evidence links are allowlisted from the selected audit package and resolved inside the
  repository; arbitrary local paths cannot be opened.
- HTML, JSON, YAML, and log evidence is served as plain text, preventing captured application
  content from executing in the dashboard origin.
- Credential values are never returned by the API. Background error messages pass through the
  same configured-secret redaction used by the audit engine.

The dashboard is a single-user local tool. Do not expose it through port forwarding, a public
proxy, or a shared host.

## Troubleshooting

- **Configuration does not appear:** run `ai-qa validate <config>`; invalid YAML is intentionally
  omitted from the selector.
- **Audit could not finish:** read the safe error shown below the Run button. Missing credentials
  are named by environment-variable name, never value.
- **Port is in use:** start with another port, for example `ai-qa dashboard --port 9123`.
- **No screenshot or trace:** failure-only evidence policies retain those files only when the
  corresponding test fails.

