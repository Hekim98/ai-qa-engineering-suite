"""Safe, evidence-producing HTTP API checks for configured QA projects."""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from pydantic import BaseModel, ValidationError

from ai_qa_engineering.config import APISettings
from ai_qa_engineering.results import APICheckOutcome, APICheckRecord
from ai_qa_engineering.secrets import ResolvedAPIAuth, redact_text

TransportResult = tuple[int, Mapping[str, str], bytes]
Transport = Callable[[Request, float, int], TransportResult]


class APICheckFailure(AssertionError):
    """Raised when an API response violates an explicit product expectation."""


class APIUnavailableError(RuntimeError):
    """Raised when an API check could not reach or read the target environment."""


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        return None


def _stdlib_transport(request: Request, timeout: float, limit: int) -> TransportResult:
    opener = build_opener(_NoRedirectHandler())
    try:
        response = opener.open(request, timeout=timeout)
    except HTTPError as exc:
        response = exc
    try:
        status = int(response.status)
        headers = {str(name): str(value) for name, value in response.headers.items()}
        body = response.read(limit + 1)
        return status, headers, body
    finally:
        response.close()


@dataclass(frozen=True)
class APIResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes
    json_body: Any
    latency_ms: float


class APIClient:
    """Execute same-origin API checks and persist redacted request/response evidence."""

    def __init__(
        self,
        settings: APISettings,
        *,
        test_id: str,
        evidence_path: Path,
        evidence_reference: str,
        auth: ResolvedAPIAuth | None = None,
        secret_values: tuple[str, ...] = (),
        transport: Transport = _stdlib_transport,
    ) -> None:
        self.settings = settings
        self.test_id = test_id
        self.evidence_path = evidence_path
        self.evidence_reference = evidence_reference
        self.auth = auth
        self.secret_values = secret_values
        self.transport = transport
        self.records: list[APICheckRecord] = []
        self._evidence: list[dict[str, Any]] = []
        parsed = urlsplit(str(settings.base_url))
        self._origin = (parsed.scheme, parsed.hostname, parsed.port)
        self._sensitive_fields = set(settings.sensitive_fields)

    def _redact_string(self, value: str) -> str:
        return redact_text(value, self.secret_values)

    def _is_sensitive(self, name: str) -> bool:
        folded = name.casefold()
        return folded in self._sensitive_fields or any(
            token in folded for token in ("password", "secret", "token", "authorization", "cookie")
        )

    def _redact_value(self, value: Any, *, field_name: str | None = None) -> Any:
        if field_name and self._is_sensitive(field_name):
            return "[REDACTED]"
        if isinstance(value, dict):
            return {
                str(key): self._redact_value(item, field_name=str(key))
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [self._redact_value(item) for item in value]
        if isinstance(value, str):
            return self._redact_string(value)
        return value

    def _safe_url(
        self,
        path: str,
        query: Mapping[str, str | int | float | bool] | None,
    ) -> tuple[str, str]:
        parsed = urlsplit(path)
        if (
            not path.startswith("/")
            or path.startswith("//")
            or parsed.scheme
            or parsed.netloc
            or parsed.fragment
            or ".." in Path(parsed.path).parts
        ):
            raise ValueError("API request paths must be safe same-origin absolute paths")
        if parsed.query and query:
            raise ValueError("Provide query parameters through either path or query, not both")
        encoded_query = parsed.query or urlencode(query or {}, doseq=False)
        relative = parsed.path + (f"?{encoded_query}" if encoded_query else "")
        url = urljoin(str(self.settings.base_url), relative)
        target = urlsplit(url)
        if (target.scheme, target.hostname, target.port) != self._origin:
            raise ValueError("API request escaped the configured origin")
        display_query = ""
        if query:
            display_query = urlencode(
                {
                    key: "[REDACTED]" if self._is_sensitive(key) else value
                    for key, value in query.items()
                }
            )
        elif parsed.query:
            display_query = "[REDACTED]"
        display_path = parsed.path + (f"?{display_query}" if display_query else "")
        return url, display_path

    def _redacted_headers(self, headers: Mapping[str, str]) -> dict[str, str]:
        return {
            name: "[REDACTED]" if self._is_sensitive(name) else self._redact_string(value)
            for name, value in headers.items()
        }

    def _persist(self) -> None:
        self.evidence_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"test": self.test_id, "checks": self._evidence}
        temporary = self.evidence_path.with_suffix(self.evidence_path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(self.evidence_path)

    @staticmethod
    def _expected_statuses(value: int | tuple[int, ...]) -> tuple[int, ...]:
        statuses = (value,) if isinstance(value, int) else tuple(dict.fromkeys(value))
        if not statuses or any(status < 100 or status > 599 for status in statuses):
            raise ValueError("expected_status must contain valid HTTP status codes")
        return statuses

    def _record(
        self,
        *,
        name: str,
        method: str,
        path: str,
        expected_statuses: tuple[int, ...],
        actual_status: int | None,
        latency_ms: float | None,
        latency_budget_ms: int,
        response_schema: str | None,
        schema_valid: bool | None,
        outcome: APICheckOutcome,
        failure_reason: str | None,
        request_headers: Mapping[str, str],
        request_body: Any,
        response_headers: Mapping[str, str] | None = None,
        response_body: Any = None,
    ) -> APICheckRecord:
        safe_reason = self._redact_string(failure_reason) if failure_reason else None
        record = APICheckRecord(
            name=name,
            test=self.test_id,
            method=method,
            path=path,
            expected_statuses=expected_statuses,
            actual_status=actual_status,
            latency_ms=latency_ms,
            latency_budget_ms=latency_budget_ms,
            response_schema=response_schema,
            schema_valid=schema_valid,
            outcome=outcome,
            evidence=self.evidence_reference,
            failure_reason=safe_reason,
        )
        self.records.append(record)
        self._evidence.append(
            {
                "check": record.model_dump(mode="json"),
                "request": {
                    "headers": self._redacted_headers(request_headers),
                    "json": self._redact_value(request_body),
                },
                "response": {
                    "headers": self._redacted_headers(response_headers or {}),
                    "body": self._redact_value(response_body),
                },
            }
        )
        self._persist()
        return record

    def check(
        self,
        name: str,
        method: str,
        path: str,
        *,
        expected_status: int | tuple[int, ...],
        response_model: type[BaseModel] | None = None,
        latency_budget_ms: int | None = None,
        json_body: Any = None,
        query: Mapping[str, str | int | float | bool] | None = None,
        headers: Mapping[str, str] | None = None,
        include_auth: bool = True,
    ) -> APIResponse:
        """Run one status/schema/latency check and retain redacted evidence."""
        if not name.strip():
            raise ValueError("API check name cannot be blank")
        normalized_method = method.upper().strip()
        if normalized_method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"}:
            raise ValueError(f"Unsupported API method: {method}")
        expected = self._expected_statuses(expected_status)
        budget = latency_budget_ms or self.settings.default_latency_budget_ms
        if budget <= 0 or budget > 60_000:
            raise ValueError("latency_budget_ms must be between 1 and 60000")
        url, display_path = self._safe_url(path, query)
        request_headers = {"Accept": "application/json", "User-Agent": "AI-QA-Engineering-Suite"}
        request_headers.update(headers or {})
        if any(name.lower() in {"host", "content-length"} for name in request_headers):
            raise ValueError("Host and Content-Length headers are transport-controlled")
        if include_auth and self.auth is not None:
            if self.auth.header_name.lower() in {name.lower() for name in request_headers}:
                raise ValueError("Configured API authentication header cannot be overridden")
            request_headers[self.auth.header_name] = self.auth.header_value.get_secret_value()
        body: bytes | None = None
        if json_body is not None:
            request_headers["Content-Type"] = "application/json"
            body = json.dumps(json_body).encode("utf-8")
        request = Request(url, data=body, headers=request_headers, method=normalized_method)
        started = time.perf_counter()
        try:
            status, response_headers, response_bytes = self.transport(
                request,
                self.settings.timeout_seconds,
                self.settings.max_response_bytes,
            )
        except (OSError, TimeoutError, URLError) as exc:
            elapsed = round((time.perf_counter() - started) * 1_000, 3)
            reason = f"Target API unavailable for {normalized_method} {display_path}: {exc}"
            self._record(
                name=name,
                method=normalized_method,
                path=display_path,
                expected_statuses=expected,
                actual_status=None,
                latency_ms=elapsed,
                latency_budget_ms=budget,
                response_schema=response_model.__name__ if response_model else None,
                schema_valid=None,
                outcome=APICheckOutcome.INCOMPLETE,
                failure_reason=reason,
                request_headers=request_headers,
                request_body=json_body,
            )
            raise APIUnavailableError(self._redact_string(reason)) from exc

        elapsed = round((time.perf_counter() - started) * 1_000, 3)
        oversized = len(response_bytes) > self.settings.max_response_bytes
        retained_body = response_bytes[: self.settings.max_response_bytes]
        parsed_body: Any = None
        try:
            parsed_body = json.loads(retained_body) if retained_body else None
        except (UnicodeDecodeError, json.JSONDecodeError):
            parsed_body = self._redact_string(retained_body.decode("utf-8", errors="replace"))

        failures: list[str] = []
        if status not in expected:
            failures.append(f"expected status {expected}, received {status}")
        if elapsed > budget:
            failures.append(f"latency {elapsed:g} ms exceeded {budget} ms budget")
        if oversized:
            failures.append(
                f"response exceeded configured {self.settings.max_response_bytes} byte limit"
            )
        schema_valid: bool | None = None
        schema_name = response_model.__name__ if response_model else None
        if response_model is not None:
            try:
                response_model.model_validate(parsed_body)
                schema_valid = True
            except ValidationError as exc:
                schema_valid = False
                failures.append(f"response schema {schema_name} failed: {exc}")

        outcome = APICheckOutcome.FAILED if failures else APICheckOutcome.PASSED
        failure_reason = "; ".join(failures) or None
        self._record(
            name=name,
            method=normalized_method,
            path=display_path,
            expected_statuses=expected,
            actual_status=status,
            latency_ms=elapsed,
            latency_budget_ms=budget,
            response_schema=schema_name,
            schema_valid=schema_valid,
            outcome=outcome,
            failure_reason=failure_reason,
            request_headers=request_headers,
            request_body=json_body,
            response_headers=response_headers,
            response_body=parsed_body,
        )
        if failures:
            raise APICheckFailure(
                f"API check '{name}' failed: {self._redact_string(failure_reason or '')}"
            )
        return APIResponse(
            status=status,
            headers=response_headers,
            body=retained_body,
            json_body=parsed_body,
            latency_ms=elapsed,
        )
