from pathlib import Path

import pytest
from playwright.sync_api import expect

from tests.saucedemo.support import SauceDemoApp

pytestmark = pytest.mark.e2e


@pytest.mark.detection_demo
def test_problem_user_reuses_incorrect_product_images(
    app: SauceDemoApp,
    qa_run_dir: Path,
) -> None:
    app.open_and_login("problem_user", "secret_sauce")
    expect(app.by_test_id("inventory-item")).to_have_count(6)

    image_sources = (
        app.by_test_id("inventory-item")
        .locator("img")
        .evaluate_all("elements => elements.map(element => element.getAttribute('src'))")
    )
    evidence_path = qa_run_dir / "test-results" / "detection-problem-user-images.png"
    app.page.screenshot(path=evidence_path, full_page=True)

    assert len(set(image_sources)) < len(image_sources), (
        "The intentionally faulty problem_user no longer demonstrates duplicate product images"
    )
