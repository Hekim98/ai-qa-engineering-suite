from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import expect

from ai_qa_engineering.config import BrowserProfile
from ai_qa_engineering.observability import BrowserObserver
from ai_qa_engineering.secrets import ResolvedCredentials
from tests.saucedemo.support import SauceDemoApp

pytestmark = pytest.mark.e2e


@pytest.mark.full
@pytest.mark.smoke
def test_standard_user_can_complete_purchase(
    app: SauceDemoApp,
    standard_credentials: ResolvedCredentials,
    browser_observer: BrowserObserver,
) -> None:
    app.open_and_login_with(standard_credentials)
    expect(app.by_test_id("title")).to_have_text("Products")

    app.add_product("sauce-labs-backpack")
    expect(app.by_test_id("shopping-cart-badge")).to_have_text("1")
    app.open_cart()
    expect(app.by_test_id("inventory-item-name")).to_have_text("Sauce Labs Backpack")

    app.begin_checkout()
    app.fill_checkout(first_name="Ada", last_name="Lovelace", postal_code="94105")
    expect(app.by_test_id("title")).to_have_text("Checkout: Overview")
    expect(app.by_test_id("total-label")).to_contain_text("$32.39")
    app.by_test_id("finish").click()

    expect(app.by_test_id("complete-header")).to_have_text("Thank you for your order!")
    assert browser_observer.console_errors == []
    assert browser_observer.failed_requests == []


@pytest.mark.full
@pytest.mark.smoke
def test_inventory_layout_fits_configured_viewport(
    app: SauceDemoApp,
    standard_credentials: ResolvedCredentials,
    qa_profile: BrowserProfile,
    qa_run_dir: Path,
) -> None:
    app.open_and_login_with(standard_credentials)

    expect(app.by_test_id("inventory-container")).to_be_visible()
    assert app.page.viewport_size == {
        "width": qa_profile.viewport.width,
        "height": qa_profile.viewport.height,
    }
    horizontal_overflow = app.page.evaluate(
        "document.documentElement.scrollWidth > document.documentElement.clientWidth"
    )
    assert horizontal_overflow is False
    if qa_profile.mobile:
        expect(app.by_test_id("shopping-cart-link")).to_be_in_viewport()
        app.page.screenshot(
            path=qa_run_dir / "test-results" / "mobile-inventory-responsive.png",
            full_page=True,
        )
