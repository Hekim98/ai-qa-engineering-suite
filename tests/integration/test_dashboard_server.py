import json
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

import pytest

from ai_qa_engineering.dashboard import DashboardHTTPServer, create_dashboard_server
from ai_qa_engineering.orchestration import AuditOutputs
from tests.dashboard_support import write_dashboard_fixture


@contextmanager
def _running_server(
    root: Path,
) -> Iterator[tuple[str, DashboardHTTPServer]]:
    audit = write_dashboard_fixture(root)

    def fake_runner(*_args: object, **_kwargs: object) -> AuditOutputs:
        return cast(AuditOutputs, SimpleNamespace(audit=audit))

    server = create_dashboard_server(root, port=0, audit_runner=fake_runner)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}", server
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


def _json_request(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, object] | None = None,
    token: str | None = None,
) -> tuple[int, dict[str, Any]]:
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    if token:
        headers["X-AI-QA-Token"] = token
    request = Request(url, data=data, headers=headers, method=method)
    with urlopen(request, timeout=3) as response:
        return response.status, json.loads(response.read())


@pytest.mark.unit
def test_dashboard_http_flow_is_local_token_protected_and_reviewable(tmp_path: Path) -> None:
    with _running_server(tmp_path) as (base_url, server):
        with urlopen(Request(f"{base_url}/health", method="HEAD"), timeout=3) as response:
            assert response.status == 200

        with urlopen(f"{base_url}/", timeout=3) as response:
            index = response.read().decode()
            assert response.status == 200
            assert "AI QA Control Room" in index
            assert "__AI_QA_TOKEN__" not in index
            assert response.headers["X-Frame-Options"] == "DENY"
            assert "default-src 'self'" in response.headers["Content-Security-Policy"]

        hostile = Request(f"{base_url}/health", headers={"Host": "attacker.example"})
        with pytest.raises(HTTPError) as rejected_host:
            urlopen(hostile, timeout=3)
        assert rejected_host.value.code == 421

        status, state = _json_request(f"{base_url}/api/state")
        assert status == 200
        audit_id = state["audits"][0]["audit_id"]

        status, detail = _json_request(f"{base_url}/api/audits/{quote(audit_id)}")
        assert status == 200
        evidence_path = detail["evidence"][0]["files"][0]["path"]
        evidence_url = (
            f"{base_url}/api/evidence/{quote(audit_id)}?{urlencode({'path': evidence_path})}"
        )
        with urlopen(evidence_url, timeout=3) as response:
            assert response.read() == b'{"fixture": true}'
            assert response.headers["Content-Type"] == "text/plain; charset=utf-8"

        with pytest.raises(HTTPError) as missing_token:
            _json_request(
                f"{base_url}/api/audits/{quote(audit_id)}/reviews",
                method="POST",
                payload={
                    "candidate_id": "AUTO-001",
                    "decision": "rejected",
                    "rationale": "Expected behavior.",
                },
            )
        assert missing_token.value.code == 403

        status, review = _json_request(
            f"{base_url}/api/audits/{quote(audit_id)}/reviews",
            method="POST",
            token=server.csrf_token,
            payload={
                "candidate_id": "AUTO-001",
                "decision": "rejected",
                "rationale": "Expected behavior.",
            },
        )
        assert status == 200
        assert review["summary"]["report_gate"] == "open"

        status, job = _json_request(
            f"{base_url}/api/audits",
            method="POST",
            token=server.csrf_token,
            payload={
                "config_path": "configs/example.yaml",
                "profiles": ["desktop-chromium"],
            },
        )
        assert status == 202
        assert job["status"] in {"queued", "running"}
        for _ in range(100):
            _, current = _json_request(f"{base_url}/api/state")
            if current["jobs"][0]["status"] == "completed":
                break
            time.sleep(0.01)
        assert current["jobs"][0]["audit_id"] == audit_id

        traversal = urlencode({"path": "../../.env"})
        with pytest.raises(HTTPError) as unsafe:
            urlopen(f"{base_url}/api/evidence/{quote(audit_id)}?{traversal}", timeout=3)
        assert unsafe.value.code == 404
