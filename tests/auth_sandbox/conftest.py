from collections.abc import Generator

import pytest
from playwright.sync_api import Page

from ai_qa_engineering.config import QAConfig
from ai_qa_engineering.observability import BrowserObserver
from tests.auth_sandbox.support import AuthSandboxApp


@pytest.fixture(autouse=True)
def capture_browser_diagnostics(browser_observer: BrowserObserver) -> Generator[None, None, None]:
    yield


@pytest.fixture
def auth_app(qa_page: Page, qa_config: QAConfig) -> AuthSandboxApp:
    app = AuthSandboxApp(qa_page, str(qa_config.project.base_url))
    app.install()
    return app
