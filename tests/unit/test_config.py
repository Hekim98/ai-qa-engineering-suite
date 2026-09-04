from pathlib import Path

import pytest

from ai_qa_engineering.config import ConfigError, EvidencePolicy, SuiteLevel, load_config


@pytest.mark.unit
def test_loads_example_configuration() -> None:
    config = load_config(Path("configs/example.yaml"))

    assert config.project.name == "demo-ai-app"
    assert str(config.project.base_url) == "https://example.com/"
    assert config.browser.profiles["desktop-chromium"].engine == "chromium"
    assert config.artifacts.screenshot is EvidencePolicy.ON_FAILURE
    assert [flow.id for flow in config.critical_flows] == ["AUTH-001", "AUTH-002"]


@pytest.mark.unit
def test_loads_saucedemo_audit_profiles() -> None:
    config = load_config(Path("configs/saucedemo.yaml"))

    assert config.browser.profiles["mobile-chromium"].viewport.width == 390
    assert config.browser.profiles["detection-chromium"].suite is SuiteLevel.DETECTION_DEMO
    assert config.security.sensitive_selectors == (
        '[data-test="username"]',
        '[data-test="password"]',
    )
    assert config.orchestration.retry_failures == 1
    assert len(config.critical_flows) == 5


@pytest.mark.unit
def test_loads_public_project_without_credentials() -> None:
    config = load_config(Path("configs/qapractice.yaml"))

    assert config.project.name == "qa-practice-store"
    assert config.credentials is None
    assert len(config.critical_flows) == 5


@pytest.mark.unit
def test_rejects_an_invalid_base_url(tmp_path: Path) -> None:
    config_file = tmp_path / "invalid.yaml"
    config_file.write_text(
        Path("configs/example.yaml")
        .read_text(encoding="utf-8")
        .replace("https://example.com", "example.com"),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="base_url"):
        load_config(config_file)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("original", "unsafe"),
    [("tests/example_project", "../outside"), ("artifacts/runs", "/tmp/runs")],
)
def test_rejects_unsafe_configured_paths(tmp_path: Path, original: str, unsafe: str) -> None:
    config_file = tmp_path / "invalid.yaml"
    config_file.write_text(
        Path("configs/example.yaml").read_text(encoding="utf-8").replace(original, unsafe),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="safe path"):
        load_config(config_file)


@pytest.mark.unit
def test_rejects_duplicate_critical_flow_ids(tmp_path: Path) -> None:
    config_file = tmp_path / "invalid.yaml"
    content = Path("configs/example.yaml").read_text(encoding="utf-8")
    config_file.write_text(content.replace("AUTH-002", "AUTH-001"), encoding="utf-8")

    with pytest.raises(ConfigError, match="unique"):
        load_config(config_file)


@pytest.mark.unit
def test_loads_named_credential_accounts(tmp_path: Path) -> None:
    config_file = tmp_path / "accounts.yaml"
    content = Path("configs/example.yaml").read_text(encoding="utf-8")
    config_file.write_text(
        content.replace(
            "  password_env: AI_QA_TEST_USER_PASSWORD\n",
            "  password_env: AI_QA_TEST_USER_PASSWORD\n"
            "  accounts:\n"
            "    admin:\n"
            "      username_env: AI_QA_ADMIN_EMAIL\n"
            "      password_env: AI_QA_ADMIN_PASSWORD\n",
        ),
        encoding="utf-8",
    )

    config = load_config(config_file)

    assert config.credentials is not None
    assert config.credentials.accounts["admin"].username_env == "AI_QA_ADMIN_EMAIL"
