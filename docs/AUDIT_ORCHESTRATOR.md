# Audit Orchestrator v1

## Purpose

The orchestrator turns isolated browser-profile executions into one reviewable audit package.
It automates execution and evidence organization, but it does not replace human QA judgment.

```text
configuration validation
  -> secret preflight
  -> browser matrix
  -> one retry for failed profiles
  -> persistent/flaky classification
  -> evidence index
  -> candidate findings
  -> unscored draft HTML/PDF
```

## Run an audit

Run every configured profile:

```bash
ai-qa audit configs/qapractice.yaml
```

Run one profile while learning or debugging:

```bash
ai-qa audit configs/qapractice.yaml --profile desktop-chromium
```

Disable the configured retry policy:

```bash
ai-qa audit configs/qapractice.yaml --no-retry
```

## Audit package

Each command creates an immutable directory:

```text
artifacts/audits/<audit-id>/
├── audit.json
├── candidate-findings.yaml
├── evidence-index.json
├── profiles/
│   ├── <initial profile run>/
│   └── <retry profile run>/
└── reports/
    ├── draft-audit-report.html
    └── draft-audit-report.pdf
```

`audit.json` is the machine-readable combined result. `candidate-findings.yaml` is a review
queue, not a verified bug list. The evidence index connects every attempt with its retained
files.

## Failure and flaky rules

- A test that fails on the initial attempt and the retry becomes a `candidate`.
- A test whose outcome changes between attempts becomes `flaky`.
- An inaccessible target or a profile that cannot produce structured results makes the audit
  `incomplete`.
- A clean audit is `passed`.
- An audit containing candidates or flaky tests is `needs-review`.

Candidate and flaky entries always set `human_verification_required: true`. Draft reports have
no score and no launch recommendation. A reviewer must reproduce and classify findings before
using the verified `ai-qa report` workflow.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | All selected profiles passed without review candidates |
| `1` | The audit completed and needs human review |
| `2` | Configuration, secret, path, or input error |
| `3` | The audit is incomplete |

## Test accounts and secret safety

The default account remains backward compatible:

```yaml
credentials:
  username_env: AI_QA_USERNAME
  password_env: AI_QA_PASSWORD
```

Optional named roles can be declared without storing values:

```yaml
credentials:
  username_env: AI_QA_USERNAME
  password_env: AI_QA_PASSWORD
  accounts:
    admin:
      username_env: AI_QA_ADMIN_USERNAME
      password_env: AI_QA_ADMIN_PASSWORD
```

Tests can request the existing `qa_credentials` fixture or resolve a role through `qa_account`:

```python
def test_admin_access(qa_account):
    admin = qa_account("admin")
```

The audit fails before launching a browser when any declared secret is missing. Secret values
are redacted from structured assertion errors, console records, and network records. Configure
selectors for fields that could appear in screenshots or video:

```yaml
security:
  sensitive_selectors:
    - "#email"
    - "#password"
```

Masking changes only the visual presentation of matching elements; tests can still interact
with them. Teams must still use dedicated non-production test accounts and synthetic data.

## Manual GitHub execution

The `Manual customer audit` workflow is available only through `workflow_dispatch`. It never
contacts an external target on push or pull request.

1. Open **Actions** in GitHub.
2. Select **Manual customer audit**.
3. Enter a repository-relative config path.
4. Optionally enter one profile, or leave it blank for the full matrix.
5. Run the workflow and download the retained audit artifact.

For authenticated projects, the generic workflow exposes repository secrets named
`AI_QA_USERNAME` and `AI_QA_PASSWORD`. The corresponding config must reference those names.
Additional role secrets should be mapped explicitly in a reviewed workflow before use.

## Current boundary

The orchestrator deliberately does not infer severity, category, expected behavior, business
impact, score, or launch recommendation. Those decisions belong to the verified audit stage.
