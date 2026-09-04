# API and Workflow QA

## Purpose

The API layer adds authenticated HTTP contract checks to the existing profile runner. API results
remain ordinary audit evidence: a failed expectation becomes a candidate for human review, while an
unreachable environment makes the audit incomplete. Browser and API checks can share one business
state and one final report.

## Configuration

An optional `api` block defines the API origin and execution boundaries:

```yaml
api:
  base_url: https://api.example.test
  auth:
    kind: bearer
    token_env: CLIENT_API_TOKEN
  timeout_seconds: 5
  default_latency_budget_ms: 1000
  max_response_bytes: 1000000
  sensitive_fields:
    - password
    - token
    - access_token
```

Authentication kinds are `none`, `bearer`, `api-key`, and `basic`. Configuration stores only
environment-variable names. Bearer and API-key auth require `token_env`; API-key auth also requires
`header_name`; basic auth requires `username_env` and `password_env`. Mismatched fields are rejected
before execution.

Request paths must begin with one `/`, stay on the configured origin, contain no traversal, and have
no fragment. Redirects are returned as status responses rather than followed, preventing credentials
from being forwarded to an unexpected location.

## Test usage

`api_client` records one redacted evidence document per test:

```python
response = api_client.check(
    "Create order",
    "POST",
    "/api/orders",
    expected_status=201,
    response_model=OrderResponse,
    latency_budget_ms=500,
    json_body={"product_id": "SKU-001", "quantity": 2},
)
```

Every check requires a name, method, path, and expected status. A Pydantic response model is optional
but recommended for material contracts. `include_auth=False` supports deliberate missing-auth tests;
an explicit invalid header can then verify invalid-auth behavior without exposing its value in
evidence.

## Evidence and failure semantics

Evidence is written below each run's `api/` directory and indexed with screenshots, traces, logs,
and browser observability files. It contains:

- safe request path and redacted headers/body;
- expected and actual status;
- response-model name and validation result;
- measured latency and declared budget;
- redacted response headers/body;
- final `passed`, `failed`, or `incomplete` outcome.

Authentication and cookie headers are always masked. Sensitive JSON keys and all configured secret
values are masked recursively. Responses are capped by `max_response_bytes`.

Status, schema, latency, or response-size violations are product-expectation failures and enter the
normal candidate-review path. Connection, DNS, read, and timeout errors produce
`APIUnavailableError`; the run is incomplete and no product candidate is created.

## Controlled proof

Run the local proof without contacting an external service:

```bash
cp .env.example .env
ai-qa audit configs/workflow-sandbox.yaml
```

The sandbox verifies catalog and error contracts, missing/invalid authentication, invalid input,
unknown resources, API order creation, browser-visible state, browser approval, API fulfillment, and
the final browser state. It uses a real loopback server with synthetic data and a fixed test token.
