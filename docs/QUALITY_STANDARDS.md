# Quality Standards

## Definition of done

A change is complete when:

1. behavior and failure modes are clear;
2. relevant automated tests pass;
3. configuration errors fail early with actionable messages;
4. secrets and generated client artifacts are not committed;
5. documentation reflects any public workflow or contract change.

## Defect severity

- **Critical:** launch-blocking data loss, security exposure, payment failure, inaccessible core journey, or another issue with severe business impact and no reasonable workaround.
- **Major:** important functionality is broken or materially degraded, but launch may be possible with a documented workaround or reduced scope.
- **Minor:** limited functional, content, consistency, or usability issue with low immediate business impact.

Severity describes impact, not how difficult a defect is to fix.

## Evidence standard

Every reportable defect should include a reproducible path, expected and actual behavior, environment details, and the smallest useful evidence set. Screenshots establish visual state; video or traces establish sequence; logs support technical diagnosis.

An automated failure is a candidate, not a verified defect. Persistent and flaky outcomes must
remain distinguishable. Neither may affect a published score or recommendation until a human has
confirmed expected behavior, reproducibility, impact, and evidence.

API evidence must identify the check, method, safe path, expected and actual status, response-model
validation, measured latency and budget, and outcome. Authentication/cookie headers, configured
secret values, and sensitive request/response fields must be replaced before persistence. Raw
tokens, passwords, session cookies, and unrestricted response bodies are not acceptable evidence.

Connection, DNS, timeout, and target-access failures are execution blockers. They mark the required
run `incomplete` and do not become product findings. Expected negative responses such as 401, 404,
409, or 422 are passing checks when their status and error contract match the declared expectation.

## Report publication standard

- Every weighted category must have one explicit status and an evidence-based rationale.
- Every configured critical flow must have one explicit status and verified evidence.
- Confirmed candidates must satisfy the complete finding contract; rejected candidates stay in
  the decision history but never enter the final report.
- HTML and PDF must be generated from the same immutable scored model.
- PDF structure, text identity, Poppler page count, and every rendered page must pass automated
  checks before visual review.
- A human must inspect all rendered pages for clipping, overflow, broken tables, and unreadable
  content before marking the report verified.
- Any material input change invalidates the visual approval and makes the previous report stale.

## Client-data handling

- Store no real credentials in configuration or source control.
- Use dedicated, least-privilege test accounts.
- Avoid copying production personal data into reports.
- Keep generated artifacts out of Git by default.
- Agree on retention and deletion expectations before a paid engagement.
- Store restorable browser session state outside evidence directories with owner-only permissions,
  and delete it automatically after the test session.
- Use only explicitly authorized targets and dedicated synthetic or least-privilege accounts.
- Bind local operator interfaces to loopback, reject non-local hosts, and token-protect every
  state-changing request.
- Treat captured HTML and logs as untrusted evidence; never execute them inside a privileged
  review origin.
