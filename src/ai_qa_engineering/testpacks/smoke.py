"""Small, broadly applicable browser health checks."""

from __future__ import annotations

import re

from playwright.sync_api import Page, expect


def assert_basic_page_health(page: Page) -> None:
    """Require a non-empty title, visible body, and one main content landmark."""
    expect(page).to_have_title(re.compile(r"\S+"))
    expect(page.locator("body")).to_be_visible()
    expect(page.locator("main")).to_have_count(1)
