import pytest
from playwright.sync_api import expect

from ai_qa_engineering.secrets import ResolvedCredentials
from tests.saucedemo.support import SauceDemoApp

pytestmark = pytest.mark.e2e


@pytest.mark.full
def test_invalid_credentials_show_actionable_error(app: SauceDemoApp) -> None:
    app.open_and_login("not-a-user", "not-a-password")

    expect(app.by_test_id("error")).to_contain_text(
        "Username and password do not match any user in this service"
    )


@pytest.mark.full
def test_locked_user_is_rejected_with_specific_error(app: SauceDemoApp) -> None:
    app.open_and_login("locked_out_user", "secret_sauce")

    expect(app.by_test_id("error")).to_contain_text("this user has been locked out")


@pytest.mark.full
def test_login_controls_follow_keyboard_order(app: SauceDemoApp) -> None:
    app.open_login()

    app.page.keyboard.press("Tab")
    expect(app.by_test_id("username")).to_be_focused()
    app.page.keyboard.press("Tab")
    expect(app.by_test_id("password")).to_be_focused()
    app.page.keyboard.press("Tab")
    expect(app.by_test_id("login-button")).to_be_focused()


@pytest.mark.full
def test_inventory_primary_controls_support_keyboard_activation(
    app: SauceDemoApp,
    standard_credentials: ResolvedCredentials,
) -> None:
    app.open_and_login_with(standard_credentials)

    add_button = app.by_test_id("add-to-cart-sauce-labs-backpack")
    add_button.focus()
    expect(add_button).to_be_focused()
    app.page.keyboard.press("Enter")
    expect(app.by_test_id("shopping-cart-badge")).to_have_text("1")

    cart_link = app.by_test_id("shopping-cart-link")
    cart_link.focus()
    expect(cart_link).to_be_focused()
    app.page.keyboard.press("Enter")
    expect(app.by_test_id("title")).to_have_text("Your Cart")
