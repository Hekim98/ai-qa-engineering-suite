from collections.abc import Generator

import pytest
from playwright.sync_api import Page

from ai_qa_engineering.config import QAConfig
from ai_qa_engineering.observability import BrowserObserver
from tests.qapractice.support import QAStoreApp


@pytest.fixture(autouse=True)
def capture_browser_diagnostics(browser_observer: BrowserObserver) -> Generator[None, None, None]:
    """Attach the shared console and network observer to every client test."""
    yield


@pytest.fixture
def store(qa_page: Page, qa_config: QAConfig) -> QAStoreApp:
    return QAStoreApp(page=qa_page, base_url=str(qa_config.project.base_url))
