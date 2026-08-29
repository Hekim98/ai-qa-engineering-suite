import pytest
from playwright.sync_api import expect

from ai_qa_engineering.observability import BrowserObserver
from ai_qa_engineering.secrets import ResolvedCredentials
from tests.saucedemo.support import SauceDemoApp

pytestmark = pytest.mark.e2e


@pytest.mark.full
@pytest.mark.parametrize(
    ("first_name", "last_name", "postal_code", "message"),
    [
        ("", "Lovelace", "94105", "First Name is required"),
        ("Ada", "", "94105", "Last Name is required"),
        ("Ada", "Lovelace", "", "Postal Code is required"),
    ],
)
def test_checkout_requires_customer_details(
    app: SauceDemoApp,
    standard_credentials: ResolvedCredentials,
    first_name: str,
    last_name: str,
    postal_code: str,
    message: str,
) -> None:
    app.open_and_login_with(standard_credentials)
    app.add_product("sauce-labs-backpack")
    app.open_cart()
    app.begin_checkout()
    app.fill_checkout(first_name=first_name, last_name=last_name, postal_code=postal_code)

    expect(app.by_test_id("error")).to_contain_text(message)


@pytest.mark.full
def test_logout_clears_access_to_inventory(
    app: SauceDemoApp,
    standard_credentials: ResolvedCredentials,
    browser_observer: BrowserObserver,
) -> None:
    app.open_and_login_with(standard_credentials)
    app.page.get_by_role("button", name="Open Menu").click()
    expect(app.by_test_id("logout-sidebar-link")).to_be_visible()
    app.by_test_id("logout-sidebar-link").click()
    expect(app.by_test_id("login-button")).to_be_visible()

    inventory_url = f"{app.base_url.rstrip('/')}/inventory.html"
    browser_observer.allow_expected(inventory_url)
    app.page.goto(inventory_url)
    expect(app.by_test_id("login-button")).to_be_visible()
    expect(app.by_test_id("error")).to_contain_text("You can only access '/inventory.html'")
    app.page.wait_for_load_state("networkidle")
