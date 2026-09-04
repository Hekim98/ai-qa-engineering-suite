"""Reusable authenticated-journey helpers with ephemeral session-state storage."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import BrowserContext, Page

from ai_qa_engineering.artifacts import safe_slug
from ai_qa_engineering.secrets import ResolvedCredentials


class SessionStateError(ValueError):
    """Raised when an ephemeral browser session cannot be loaded safely."""


@dataclass(frozen=True)
class LoginForm:
    """Selectors and actions shared by conventional username/password forms."""

    page: Page
    username_selector: str
    password_selector: str
    submit_selector: str

    def submit(self, credentials: ResolvedCredentials) -> None:
        self.page.locator(self.username_selector).fill(credentials.username.get_secret_value())
        self.page.locator(self.password_selector).fill(credentials.password.get_secret_value())
        self.page.locator(self.submit_selector).click()


class SessionStateStore:
    """Keep Playwright storage state outside audit artifacts with private permissions."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.root.chmod(0o700)

    def _path(self, account_name: str) -> Path:
        return self.root / f"{safe_slug(account_name)}.json"

    def save(self, context: BrowserContext, account_name: str) -> Path:
        path = self._path(account_name)
        context.storage_state(path=path)
        path.chmod(0o600)
        return path

    def load(self, account_name: str) -> Path:
        path = self._path(account_name)
        if not path.is_file():
            raise SessionStateError(f"Session state not found for account: {account_name}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise SessionStateError(f"Invalid session state for account: {account_name}") from exc
        if not isinstance(payload, dict) or not {"cookies", "origins"}.issubset(payload):
            raise SessionStateError(f"Invalid session state for account: {account_name}")
        path.chmod(0o600)
        return path

    def clear(self, account_name: str) -> None:
        path = self._path(account_name)
        if path.exists():
            path.unlink()
