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

## Client-data handling

- Store no real credentials in configuration or source control.
- Use dedicated, least-privilege test accounts.
- Avoid copying production personal data into reports.
- Keep generated artifacts out of Git by default.
- Agree on retention and deletion expectations before a paid engagement.
