"""Navigation helpers that distinguish unavailable targets from product failures."""

from __future__ import annotations

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, Response, TimeoutError


class TargetUnavailableError(RuntimeError):
    """Raised when an environment cannot be reached reliably enough to test."""


def navigate_or_incomplete(
    page: Page,
    url: str,
    *,
    timeout_ms: int = 30_000,
) -> Response | None:
    """Navigate to a target and classify transport/server failures as incomplete."""
    try:
        response = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
    except (PlaywrightError, TimeoutError) as exc:
        raise TargetUnavailableError(f"Target environment is unavailable: {url}") from exc
    if response is not None and response.status >= 500:
        raise TargetUnavailableError(f"Target environment returned HTTP {response.status}: {url}")
    return response
