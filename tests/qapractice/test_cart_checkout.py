import pytest
from playwright.sync_api import expect

from ai_qa_engineering.observability import BrowserObserver
from tests.qapractice.support import QAStoreApp

pytestmark = pytest.mark.e2e


@pytest.mark.full
def test_empty_cart_blocks_checkout(store: QAStoreApp) -> None:
    store.open_catalog()
    store.open_cart()

    expect(store.by_test_id("ecom-proceed-to-buy")).to_be_disabled()


@pytest.mark.full
def test_shopper_can_remove_cart_item(store: QAStoreApp) -> None:
    store.open_catalog()
    store.add_product(2, quantity=2)
    store.open_cart()

    expect(store.by_test_id("remove-from-cart-2")).to_be_visible()
    expect(store.by_test_id("ecom-cart-button")).to_have_text("2")
    store.by_test_id("remove-from-cart-2").click()
    expect(store.by_test_id("remove-from-cart-2")).to_have_count(0)
    expect(store.by_test_id("ecom-proceed-to-buy")).to_be_disabled()


@pytest.mark.full
@pytest.mark.smoke
def test_shopper_can_complete_dummy_checkout(
    store: QAStoreApp,
    browser_observer: BrowserObserver,
) -> None:
    store.open_catalog()
    store.add_product(2, quantity=2)
    store.enter_checkout()
    store.fill_address()
    store.complete_dummy_payment()

    expect(store.by_test_id("ecom-order-success")).to_contain_text("Order Successful")
    assert browser_observer.console_errors == []
    assert browser_observer.failed_requests == []
