from collections.abc import Callable
from pathlib import Path

import pytest
from playwright.sync_api import BrowserContext, expect

from ai_qa_engineering.auth import SessionStateStore
from ai_qa_engineering.secrets import ResolvedCredentials
from tests.auth_sandbox.support import AuthSandboxApp


@pytest.mark.full
@pytest.mark.smoke
def test_member_login_and_session_restore(
    auth_app: AuthSandboxApp,
    qa_credentials: ResolvedCredentials,
    qa_context_factory: Callable[..., BrowserContext],
    qa_session_store: SessionStateStore,
    qa_run_dir: Path,
) -> None:
    auth_app.open_login()
    auth_app.login(qa_credentials)
    expect(auth_app.page.get_by_role("heading", name="Account dashboard")).to_be_visible()
    expect(auth_app.page.locator("#role")).to_have_text("member")

    state_path = qa_session_store.save(auth_app.page.context, "member")
    assert not state_path.is_relative_to(qa_run_dir)
    assert state_path.stat().st_mode & 0o777 == 0o600

    restored_context = qa_context_factory(storage_state=str(qa_session_store.load("member")))
    restored_page = restored_context.new_page()
    restored_app = AuthSandboxApp(restored_page, auth_app.base_url)
    restored_app.install()
    restored_app.open_dashboard()

    expect(restored_page.get_by_role("heading", name="Account dashboard")).to_be_visible()
    expect(restored_page.locator("#identity")).to_have_text("member@example.test")


@pytest.mark.full
@pytest.mark.smoke
def test_logout_invalidates_session(
    auth_app: AuthSandboxApp,
    qa_credentials: ResolvedCredentials,
) -> None:
    auth_app.open_login()
    auth_app.login(qa_credentials)
    auth_app.logout()

    expect(auth_app.page.get_by_role("heading", name="Sign in")).to_be_visible()
    expect(auth_app.page.locator("#notice")).to_have_text("Signed out")
    auth_app.open_dashboard()
    expect(auth_app.page.get_by_role("heading", name="Sign in")).to_be_visible()


@pytest.mark.full
def test_role_boundaries(
    auth_app: AuthSandboxApp,
    qa_credentials: ResolvedCredentials,
    qa_account: Callable[[str], ResolvedCredentials],
) -> None:
    auth_app.open_login()
    auth_app.login(qa_credentials)
    auth_app.open_admin()
    expect(auth_app.page.get_by_role("heading", name="Access denied")).to_be_visible()

    auth_app.open_login()
    auth_app.login(qa_account("admin"))
    auth_app.open_admin()
    expect(auth_app.page.get_by_role("heading", name="Admin area")).to_be_visible()


@pytest.mark.full
def test_locked_and_invalid_credentials(
    auth_app: AuthSandboxApp,
    qa_account: Callable[[str], ResolvedCredentials],
) -> None:
    auth_app.open_login()
    auth_app.login_values("unknown@example.test", "incorrect")
    expect(auth_app.page.locator("#notice")).to_have_text("Invalid credentials")

    auth_app.login(qa_account("locked"))
    expect(auth_app.page.locator("#notice")).to_have_text("Account locked")


@pytest.mark.full
def test_expiration_and_private_recovery(
    auth_app: AuthSandboxApp,
    qa_credentials: ResolvedCredentials,
) -> None:
    auth_app.open_login()
    auth_app.login(qa_credentials)
    auth_app.expire_session()
    expect(auth_app.page.get_by_role("heading", name="Sign in")).to_be_visible()
    expect(auth_app.page.locator("#notice")).to_have_text("Session expired")

    known_response = auth_app.request_recovery("member@example.test")
    unknown_response = auth_app.request_recovery("missing@example.test")
    assert known_response == unknown_response
    assert known_response == "If the account exists, recovery instructions will be sent."
