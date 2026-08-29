import pytest

from ai_qa_engineering.secrets import ResolvedCredentials
from tests.saucedemo.support import SauceDemoApp

pytestmark = pytest.mark.e2e


@pytest.mark.full
def test_inventory_has_basic_semantic_landmarks(
    app: SauceDemoApp,
    standard_credentials: ResolvedCredentials,
) -> None:
    app.open_and_login_with(standard_credentials)

    issues: list[str] = []
    if app.page.locator("main").count() != 1:
        issues.append("inventory must expose exactly one main landmark")
    if app.page.get_by_role("heading", level=1).count() != 1:
        issues.append("inventory must expose exactly one level-one heading")
    assert issues == [], "; ".join(issues)
