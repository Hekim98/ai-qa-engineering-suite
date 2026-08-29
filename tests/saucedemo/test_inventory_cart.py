import pytest
from playwright.sync_api import expect

from ai_qa_engineering.observability import BrowserObserver
from ai_qa_engineering.secrets import ResolvedCredentials
from tests.saucedemo.support import SauceDemoApp

pytestmark = pytest.mark.e2e


@pytest.mark.full
def test_inventory_can_be_sorted_by_price(
    app: SauceDemoApp,
    standard_credentials: ResolvedCredentials,
) -> None:
    app.open_and_login_with(standard_credentials)
    assert len(app.inventory_names()) == 6

    app.by_test_id("product-sort-container").select_option("lohi")
    prices = app.inventory_prices()
    assert prices == sorted(prices)


@pytest.mark.full
def test_cart_state_survives_reload_and_remove(
    app: SauceDemoApp,
    standard_credentials: ResolvedCredentials,
    browser_observer: BrowserObserver,
) -> None:
    app.open_and_login_with(standard_credentials)
    app.add_product("sauce-labs-backpack")
    app.add_product("sauce-labs-bike-light")
    app.page.reload()

    expect(app.by_test_id("shopping-cart-badge")).to_have_text("2")
    app.open_cart()
    expect(app.by_test_id("inventory-item")).to_have_count(2)
    app.by_test_id("remove-sauce-labs-bike-light").click()
    expect(app.by_test_id("inventory-item")).to_have_count(1)
    expect(app.by_test_id("inventory-item-name")).to_have_text("Sauce Labs Backpack")
    assert browser_observer.console_errors == []
    assert browser_observer.failed_requests == []
