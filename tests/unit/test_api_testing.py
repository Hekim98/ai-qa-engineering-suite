from __future__ import annotations

import json
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request

import pytest
from pydantic import BaseModel, ConfigDict, SecretStr

from ai_qa_engineering.api_testing import APICheckFailure, APIClient, APIUnavailableError
from ai_qa_engineering.config import APISettings
from ai_qa_engineering.results import APICheckOutcome
from ai_qa_engineering.secrets import ResolvedAPIAuth


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    token: str


def _settings() -> APISettings:
    return APISettings(base_url="https://api.example.test", default_latency_budget_ms=500)


@pytest.mark.unit
def test_api_client_validates_and_persists_redacted_evidence(tmp_path: Path) -> None:
    def transport(
        request: Request, _timeout: float, _limit: int
    ) -> tuple[int, dict[str, str], bytes]:
        assert request.get_header("Authorization") == "Bearer private-token"
        return 200, {"Set-Cookie": "private-token"}, b'{"id":"one","token":"private-token"}'

    evidence = tmp_path / "api/check.json"
    client = APIClient(
        _settings(),
        test_id="tests/demo.py::test_contract",
        evidence_path=evidence,
        evidence_reference="api/check.json",
        auth=ResolvedAPIAuth("Authorization", SecretStr("Bearer private-token")),
        secret_values=("private-token",),
        transport=transport,
    )

    response = client.check(
        "Read resource",
        "GET",
        "/resources/one",
        query={"view": "summary", "access_token": "private-token"},
        expected_status=200,
        response_model=Payload,
    )

    persisted = evidence.read_text(encoding="utf-8")
    payload = json.loads(persisted)
    assert response.status == 200
    assert client.records[0].outcome is APICheckOutcome.PASSED
    assert client.records[0].path == "/resources/one?view=summary&access_token=%5BREDACTED%5D"
    assert payload["checks"][0]["request"]["headers"]["Authorization"] == "[REDACTED]"
    assert payload["checks"][0]["response"]["body"]["token"] == "[REDACTED]"
    assert "private-token" not in persisted


@pytest.mark.unit
def test_api_client_records_status_and_schema_failures(tmp_path: Path) -> None:
    def transport(
        _request: Request, _timeout: float, _limit: int
    ) -> tuple[int, dict[str, str], bytes]:
        return 500, {"Content-Type": "application/json"}, b'{"unexpected":true}'

    client = APIClient(
        _settings(),
        test_id="tests/demo.py::test_failure",
        evidence_path=tmp_path / "api/failure.json",
        evidence_reference="api/failure.json",
        transport=transport,
    )

    with pytest.raises(APICheckFailure, match="expected status"):
        client.check(
            "Broken contract",
            "GET",
            "/resources/one",
            expected_status=200,
            response_model=Payload,
        )

    assert client.records[0].outcome is APICheckOutcome.FAILED
    assert client.records[0].schema_valid is False
    assert "response schema Payload failed" in (client.records[0].failure_reason or "")


@pytest.mark.unit
def test_api_client_enforces_latency_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = iter((10.0, 10.75))
    monkeypatch.setattr("ai_qa_engineering.api_testing.time.perf_counter", lambda: next(clock))

    def transport(
        _request: Request, _timeout: float, _limit: int
    ) -> tuple[int, dict[str, str], bytes]:
        return 200, {}, b'{"id":"one","token":"safe"}'

    client = APIClient(
        _settings(),
        test_id="tests/demo.py::test_latency",
        evidence_path=tmp_path / "api/latency.json",
        evidence_reference="api/latency.json",
        transport=transport,
    )

    with pytest.raises(APICheckFailure, match="exceeded 500 ms budget"):
        client.check(
            "Latency budget",
            "GET",
            "/resources/one",
            expected_status=200,
            response_model=Payload,
        )

    assert client.records[0].latency_ms == 750


@pytest.mark.unit
def test_api_client_marks_transport_failure_incomplete(tmp_path: Path) -> None:
    def unavailable(
        _request: Request, _timeout: float, _limit: int
    ) -> tuple[int, dict[str, str], bytes]:
        raise URLError("connection refused")

    client = APIClient(
        _settings(),
        test_id="tests/demo.py::test_unavailable",
        evidence_path=tmp_path / "api/unavailable.json",
        evidence_reference="api/unavailable.json",
        transport=unavailable,
    )

    with pytest.raises(APIUnavailableError, match="Target API unavailable"):
        client.check("Unavailable target", "GET", "/health", expected_status=200)

    assert client.records[0].outcome is APICheckOutcome.INCOMPLETE
    assert client.records[0].actual_status is None


@pytest.mark.unit
@pytest.mark.parametrize("path", ["relative", "//other.test/path", "/../secret", "/ok#fragment"])
def test_api_client_rejects_paths_that_can_escape_or_hide_the_origin(
    tmp_path: Path, path: str
) -> None:
    client = APIClient(
        _settings(),
        test_id="tests/demo.py::test_path",
        evidence_path=tmp_path / "api/path.json",
        evidence_reference="api/path.json",
    )

    with pytest.raises(ValueError, match="safe same-origin"):
        client.check("Unsafe path", "GET", path, expected_status=200)
