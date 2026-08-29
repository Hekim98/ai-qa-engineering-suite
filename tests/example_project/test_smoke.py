import pytest
from playwright.sync_api import Page

from ai_qa_engineering.observability import BrowserObserver
from ai_qa_engineering.testpacks import assert_basic_page_health


@pytest.mark.full
@pytest.mark.smoke
def test_local_example_page_is_healthy(
    qa_page: Page,
    browser_observer: BrowserObserver,
) -> None:
    qa_page.set_content(
        """
        <html>
          <head><title>AI QA Example</title></head>
          <body><main><h1>Ready for QA</h1></main></body>
        </html>
        """
    )

    assert qa_page.viewport_size == {"width": 1440, "height": 900}
    assert_basic_page_health(qa_page)
    assert browser_observer.console_errors == []
    assert browser_observer.failed_requests == []
