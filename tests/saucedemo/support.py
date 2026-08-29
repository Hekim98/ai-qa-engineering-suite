"""Client-specific SauceDemo actions kept outside the reusable core engine."""

from __future__ import annotations

from dataclasses import dataclass

from playwright.sync_api import Locator, Page

from ai_qa_engineering.navigation import navigate_or_incomplete
from ai_qa_engineering.secrets import ResolvedCredentials


@dataclass(frozen=True)
class SauceDemoApp:
    page: Page
    base_url: str

    def by_test_id(self, value: str) -> Locator:
        return self.page.locator(f'[data-test="{value}"]')

    def open_login(self) -> None:
        navigate_or_incomplete(self.page, self.base_url)

    def login(self, username: str, password: str) -> None:
        self.by_test_id("username").fill(username)
        self.by_test_id("password").fill(password)
        self.by_test_id("login-button").click()

    def open_and_login(self, username: str, password: str) -> None:
        self.open_login()
        self.login(username, password)

    def open_and_login_with(self, credentials: ResolvedCredentials) -> None:
        self.open_and_login(
            credentials.username.get_secret_value(),
            credentials.password.get_secret_value(),
        )

    def add_product(self, product_slug: str) -> None:
        self.by_test_id(f"add-to-cart-{product_slug}").click()

    def open_cart(self) -> None:
        self.by_test_id("shopping-cart-link").click()

    def begin_checkout(self) -> None:
        self.by_test_id("checkout").click()

    def fill_checkout(self, *, first_name: str, last_name: str, postal_code: str) -> None:
        self.by_test_id("firstName").fill(first_name)
        self.by_test_id("lastName").fill(last_name)
        self.by_test_id("postalCode").fill(postal_code)
        self.by_test_id("continue").click()

    def inventory_names(self) -> list[str]:
        return self.by_test_id("inventory-item-name").all_text_contents()

    def inventory_prices(self) -> list[float]:
        return [
            float(value.removeprefix("$"))
            for value in self.by_test_id("inventory-item-price").all_text_contents()
        ]
