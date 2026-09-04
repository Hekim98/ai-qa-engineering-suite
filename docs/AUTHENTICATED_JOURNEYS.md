# Authenticated Journeys

## Purpose

This milestone proves that the suite can test authenticated behavior without using a real
customer account or contacting an uncontrolled website. The target is a deterministic browser
sandbox intercepted entirely inside Playwright. It behaves like a small application, but no
request reaches the public internet.

## Covered risks

The controlled audit exercises:

- valid member authentication;
- invalid and locked credentials;
- session restoration in a new browser context;
- logout and expired-session handling;
- member-versus-administrator authorization boundaries;
- account-recovery privacy for known and unknown email addresses;
- desktop, mobile, Chromium, Firefox, and WebKit profiles.

The fixed accounts are synthetic and safe to keep in `.env.example`. Real client credentials
must remain in environment variables or an ignored local `.env` file.

## Session-state design

`SessionStateStore` asks Playwright to export cookies and web-storage state to an operating-system
temporary directory. The directory is owner-only (`0700`), each state file is owner-only (`0600`),
and the complete directory is deleted when the Pytest session finishes. Session files are never
placed in the audit package, evidence index, report, or Git history.

Tests restore a session through the profile-aware context factory:

```python
state_path = qa_session_store.save(qa_page.context, "member")
context = qa_context_factory(storage_state=str(state_path))
page = context.new_page()
```

`LoginForm` provides the conventional username/password/submit sequence. Product-specific tests
still own selectors and successful-login assertions because those are part of the client's
behavior, not the core engine.

## Run locally

Copy the example environment once, or export the six `AUTH_SANDBOX_*` values shown there:

```bash
cp .env.example .env
ai-qa validate configs/auth-sandbox.yaml
ai-qa audit configs/auth-sandbox.yaml
```

For a faster learning loop, run only the main profile:

```bash
ai-qa audit configs/auth-sandbox.yaml --profile desktop-chromium
```

The complete output is written below `artifacts/audits/<audit-id>/`. A successful run contains
structured profile results and unscored draft reports. It does not publish a launch-readiness
score because automation output still requires human verification.

## Verified reference run

The complete matrix was verified locally on 2026-09-04:

| Profile | Browser | Selected tests | Result |
| --- | --- | ---: | --- |
| desktop-chromium | Chromium | 5 | Passed |
| mobile-chromium | Chromium | 2 | Passed |
| desktop-firefox | Firefox | 2 | Passed |
| desktop-webkit | WebKit | 2 | Passed |

All 11 selected tests passed with zero persistent failures, flaky tests, or candidate findings.
The generated audit package was scanned for all six synthetic credential values and the saved
`member.json` storage state; none was persisted. Its one-page PDF draft was checked with
`pdfinfo`, text extraction, and a full-page PNG render.

## Adapt for an authorized client

1. Obtain written authorization, target URLs, dedicated test accounts, roles, and data-retention
   expectations.
2. Create a new config whose credential fields contain environment-variable names only.
3. Keep login selectors and product assertions in the client test layer.
4. Use the default account for the normal customer journey and named accounts for role-specific
   boundaries.
5. Save session state only through `qa_session_store`; never copy it into `artifacts/` or `output/`.
6. Confirm logout, expiry, recovery, and least-privilege behavior before reviewing findings.

Do not use personal accounts, production personal data, or targets without explicit permission.

## Verification boundary

The sandbox demonstrates framework capability, not the security of a real identity provider.
It intentionally excludes MFA, email delivery, social login, CAPTCHA, SSO, device trust, and
server-side token revocation. Those require an authorized environment and client-specific scope.
