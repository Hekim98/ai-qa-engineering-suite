import pytest
from playwright.sync_api import Page

from ai_qa_engineering.observability import BrowserObserver
from ai_qa_engineering.testpacks import assert_basic_page_health


@pytest.mark.full
@pytest.mark.smoke
def test_local_example_page_is_healthy(
    page: Page,
    browser_observer: BrowserObserver,
) -> None:
    page.set_content(
        """
        <html>
          <head><title>AI QA Example</title></head>
          <body><main><h1>Ready for QA</h1></main></body>
        </html>
        """
    )

    assert_basic_page_health(page)
    assert browser_observer.console_errors == []
    assert browser_observer.failed_requests == []
