from __future__ import annotations

from dataclasses import dataclass

from playwright.sync_api import Locator, Page, expect

from ai_qa_engineering.navigation import navigate_or_incomplete


@dataclass(frozen=True)
class QAStoreApp:
    page: Page
    base_url: str

    def by_test_id(self, value: str) -> Locator:
        return self.page.get_by_test_id(value)

    def open_catalog(self) -> None:
        navigate_or_incomplete(self.page, self.base_url)
        expect(self.by_test_id("ecom-result-count")).to_be_visible(timeout=15_000)

    def reveal_search(self) -> None:
        search = self.by_test_id("ecom-search")
        if not search.is_visible():
            store_navigation = self.page.locator("nav").filter(has=search)
            store_navigation.get_by_role("button", name="Toggle navigation").click()
        expect(search).to_be_visible()

    def add_product(self, product_id: int, *, quantity: int = 1) -> None:
        self.by_test_id(f"quantity-{product_id}").fill(str(quantity))
        self.by_test_id(f"add-to-cart-{product_id}").click()

    def open_cart(self) -> None:
        self.by_test_id("ecom-cart-button").click()

    def enter_checkout(self) -> None:
        self.open_cart()
        self.by_test_id("ecom-proceed-to-buy").click()

    def fill_address(self) -> None:
        self.by_test_id("ecom-address-name").fill("Ada Lovelace")
        self.by_test_id("ecom-address-street").fill("1 Analytical Ave")
        self.by_test_id("ecom-address-city").fill("London")
        self.by_test_id("ecom-address-state").fill("LDN")
        self.by_test_id("ecom-address-zip").fill("EC1A")
        self.by_test_id("ecom-save-address").click()

    def complete_dummy_payment(self) -> None:
        self.by_test_id("ecom-card-number").fill("4111111111111111")
        self.by_test_id("ecom-expiry").fill("12/30")
        self.by_test_id("ecom-cvv").fill("123")
        self.by_test_id("ecom-buy-now").click()
