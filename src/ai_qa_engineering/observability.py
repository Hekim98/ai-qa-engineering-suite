"""Collect browser console and network failures without evaluating product correctness."""

from __future__ import annotations

from playwright.sync_api import ConsoleMessage, Page, Request, Response

from ai_qa_engineering.results import ConsoleRecord, NetworkRecord


class BrowserObserver:
    """Capture browser diagnostics while respecting a configured allowlist."""

    def __init__(self, allowlist: tuple[str, ...] = ()) -> None:
        self.allowlist = allowlist
        self.console_errors: list[ConsoleRecord] = []
        self.failed_requests: list[NetworkRecord] = []

    def _allowed(self, value: str) -> bool:
        return any(token in value for token in self.allowlist)

    def record_console(self, *, level: str, text: str, url: str | None = None) -> None:
        if level != "error" or self._allowed(f"{url or ''} {text}"):
            return
        self.console_errors.append(ConsoleRecord(level=level, text=text, url=url))

    def record_request_failure(
        self,
        *,
        url: str,
        method: str,
        reason: str,
        status: int | None = None,
    ) -> None:
        if self._allowed(url):
            return
        self.failed_requests.append(
            NetworkRecord(url=url, method=method, reason=reason, status=status)
        )

    def attach(self, page: Page) -> None:
        page.on("console", self._on_console)
        page.on("requestfailed", self._on_request_failed)
        page.on("response", self._on_response)

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
