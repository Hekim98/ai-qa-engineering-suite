"""Collect browser console and network failures without evaluating product correctness."""

from __future__ import annotations

from collections.abc import Callable

from playwright.sync_api import ConsoleMessage, Page, Request, Response

from ai_qa_engineering.results import ConsoleRecord, NetworkRecord


class BrowserObserver:
    """Capture browser diagnostics while respecting a configured allowlist."""

    def __init__(
        self,
        allowlist: tuple[str, ...] = (),
        *,
        capture_console_errors: bool = True,
        capture_failed_requests: bool = True,
        redact: Callable[[str], str] | None = None,
    ) -> None:
        self.allowlist = allowlist
        self.capture_console_errors = capture_console_errors
        self.capture_failed_requests = capture_failed_requests
        self.redact = redact or (lambda value: value)
        self.console_errors: list[ConsoleRecord] = []
        self.failed_requests: list[NetworkRecord] = []

    def _allowed(self, value: str) -> bool:
        return any(token in value for token in self.allowlist)

    def record_console(self, *, level: str, text: str, url: str | None = None) -> None:
        if (
            not self.capture_console_errors
            or level != "error"
            or self._allowed(f"{url or ''} {text}")
        ):
            return
        self.console_errors.append(
            ConsoleRecord(
                level=level,
                text=self.redact(text),
                url=self.redact(url) if url else None,
            )
        )

    def record_request_failure(
        self,
        *,
        url: str,
        method: str,
        reason: str,
        status: int | None = None,
    ) -> None:
        if not self.capture_failed_requests or self._allowed(url):
            return
        self.failed_requests.append(
            NetworkRecord(
                url=self.redact(url),
                method=method,
                reason=self.redact(reason),
                status=status,
            )
        )

    def attach(self, page: Page) -> None:
        page.on("console", self._on_console)
        page.on("requestfailed", self._on_request_failed)
        page.on("response", self._on_response)

    def discard_expected(self, token: str) -> None:
        """Remove failures produced deliberately by a negative-path test."""
        self.console_errors[:] = [
            record
            for record in self.console_errors
            if token not in f"{record.url or ''} {record.text}"
        ]
        self.failed_requests[:] = [
            record for record in self.failed_requests if token not in record.url
        ]

    def allow_expected(self, token: str) -> None:
        """Ignore current and later browser events caused by an intentional failure path."""
        self.allowlist = (*self.allowlist, token)
        self.discard_expected(token)

    def _on_console(self, message: ConsoleMessage) -> None:
        location = message.location
        self.record_console(
            level=message.type,
            text=message.text,
            url=str(location.get("url")) if location.get("url") else None,
        )

    def _on_request_failed(self, request: Request) -> None:
        self.record_request_failure(
            url=request.url,
            method=request.method,
            reason=request.failure or "request failed",
        )

    def _on_response(self, response: Response) -> None:
        if response.status < 400:
            return
        self.record_request_failure(
            url=response.url,
            method=response.request.method,
            reason=f"HTTP {response.status}",
            status=response.status,
        )
