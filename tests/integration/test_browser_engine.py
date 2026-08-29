from pathlib import Path

import pytest
from playwright.sync_api import Playwright

from ai_qa_engineering.observability import BrowserObserver
from ai_qa_engineering.testpacks import assert_basic_page_health


@pytest.mark.integration
def test_local_browser_captures_evidence_and_network_failure(
    playwright: Playwright,
    tmp_path: Path,
) -> None:
    browser = playwright.chromium.launch()
    video_dir = tmp_path / "video"
    context = browser.new_context(record_video_dir=video_dir)
    context.tracing.start(screenshots=True, snapshots=True, sources=True)
    page = context.new_page()
    observer = BrowserObserver()
    observer.attach(page)
    page.route("https://example.test/broken", lambda route: route.abort("failed"))
    page.set_content(
        """
        <html>
          <head><title>Local Browser Fixture</title></head>
          <body><main><h1>Fixture</h1></main></body>
        </html>
        """
    )
    assert_basic_page_health(page)
    page.evaluate("fetch('https://example.test/broken').catch(() => undefined)")
    page.screenshot(path=tmp_path / "page.png")
    context.tracing.stop(path=tmp_path / "trace.zip")
    context.close()
    browser.close()

    assert (tmp_path / "page.png").stat().st_size > 0
    assert (tmp_path / "trace.zip").stat().st_size > 0
    assert any(video_dir.glob("*.webm"))
    assert [record.url for record in observer.failed_requests] == ["https://example.test/broken"]
