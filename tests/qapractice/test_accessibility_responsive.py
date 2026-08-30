from pathlib import Path

import pytest
from playwright.sync_api import expect

from ai_qa_engineering.config import BrowserProfile
from ai_qa_engineering.testpacks import assert_basic_page_health
from tests.qapractice.support import QAStoreApp

pytestmark = pytest.mark.e2e


@pytest.mark.full
def test_catalog_has_basic_semantic_landmarks(store: QAStoreApp) -> None:
    store.open_catalog()

    assert_basic_page_health(store.page)
    expect(store.page.locator("h1")).to_have_count(1)
    expect(store.page.locator("img:not([alt])")).to_have_count(0)


@pytest.mark.full
@pytest.mark.smoke
def test_catalog_fits_configured_viewport(
    store: QAStoreApp,
    qa_profile: BrowserProfile,
    qa_run_dir: Path,
) -> None:
    store.open_catalog()

    assert store.page.viewport_size == {
        "width": qa_profile.viewport.width,
        "height": qa_profile.viewport.height,
    }
    horizontal_overflow = store.page.evaluate(
        "document.documentElement.scrollWidth > document.documentElement.clientWidth"
    )
    assert horizontal_overflow is False
    store.reveal_search()
    expect(store.by_test_id("ecom-search")).to_be_in_viewport()
    if qa_profile.mobile:
        store.page.screenshot(
            path=qa_run_dir / "test-results" / "mobile-catalog-responsive.png",
            full_page=True,
        )
