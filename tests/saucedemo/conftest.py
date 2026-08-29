from collections.abc import Generator

import pytest
from playwright.sync_api import Page

from ai_qa_engineering.config import QAConfig
from ai_qa_engineering.observability import BrowserObserver
from ai_qa_engineering.secrets import ResolvedCredentials
from tests.saucedemo.support import SauceDemoApp


@pytest.fixture(autouse=True)
def capture_browser_diagnostics(browser_observer: BrowserObserver) -> Generator[None, None, None]:
    """Attach console and network diagnostics to every audit test."""
    yield


@pytest.fixture
def app(qa_page: Page, qa_config: QAConfig) -> SauceDemoApp:
    return SauceDemoApp(page=qa_page, base_url=str(qa_config.project.base_url))


@pytest.fixture(scope="session")
def standard_credentials(qa_credentials: ResolvedCredentials) -> ResolvedCredentials:
    return qa_credentials
