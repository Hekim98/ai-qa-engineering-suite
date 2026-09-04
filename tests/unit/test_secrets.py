from pathlib import Path

import pytest

from ai_qa_engineering.config import CredentialAccountSettings, CredentialSettings
from ai_qa_engineering.secrets import (
    MissingSecretError,
    available_secret_values,
    configured_secret_names,
    redact_text,
    resolve_accounts,
    resolve_credentials,
)

SETTINGS = CredentialSettings(
    username_env="AI_QA_TEST_USER_EMAIL",
    password_env="AI_QA_TEST_USER_PASSWORD",
)


@pytest.mark.unit
def test_resolves_credentials_from_env_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "AI_QA_TEST_USER_EMAIL=file@example.com\nAI_QA_TEST_USER_PASSWORD=file-secret\n",
        encoding="utf-8",
    )

    credentials = resolve_credentials(SETTINGS, env_file=env_file)

    assert credentials.username.get_secret_value() == "file@example.com"
    assert credentials.password.get_secret_value() == "file-secret"
    assert "file-secret" not in repr(credentials.password)


@pytest.mark.unit
def test_process_environment_takes_precedence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "AI_QA_TEST_USER_EMAIL=file@example.com\nAI_QA_TEST_USER_PASSWORD=file-secret\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AI_QA_TEST_USER_EMAIL", "process@example.com")
    monkeypatch.setenv("AI_QA_TEST_USER_PASSWORD", "process-secret")

    credentials = resolve_credentials(SETTINGS, env_file=env_file)

    assert credentials.username.get_secret_value() == "process@example.com"
    assert credentials.password.get_secret_value() == "process-secret"


@pytest.mark.unit
def test_missing_secret_names_variable_without_leaking_values(tmp_path: Path) -> None:
    with pytest.raises(MissingSecretError, match="AI_QA_TEST_USER_EMAIL"):
        resolve_credentials(SETTINGS, env_file=tmp_path / "missing.env")


@pytest.mark.unit
def test_resolves_named_accounts_and_redacts_all_available_values(tmp_path: Path) -> None:
    settings = CredentialSettings(
        username_env="AI_QA_TEST_USER_EMAIL",
        password_env="AI_QA_TEST_USER_PASSWORD",
        accounts={
            "admin": CredentialAccountSettings(
                username_env="AI_QA_ADMIN_EMAIL",
                password_env="AI_QA_ADMIN_PASSWORD",
            )
        },
    )
    env_file = tmp_path / ".env"
    env_file.write_text(
        "AI_QA_TEST_USER_EMAIL=user@example.com\n"
        "AI_QA_TEST_USER_PASSWORD=user-secret\n"
        "AI_QA_ADMIN_EMAIL=admin@example.com\n"
        "AI_QA_ADMIN_PASSWORD=admin-secret\n",
        encoding="utf-8",
    )

    accounts = resolve_accounts(settings, env_file=env_file)
    values = available_secret_values(settings, env_file=env_file)
    redacted = redact_text(
        "user@example.com used user-secret; admin@example.com used admin-secret", values
    )

    assert set(accounts) == {"default", "admin"}
    assert accounts["admin"].username.get_secret_value() == "admin@example.com"
    assert configured_secret_names(settings) == (
        "AI_QA_TEST_USER_EMAIL",
        "AI_QA_TEST_USER_PASSWORD",
        "AI_QA_ADMIN_EMAIL",
        "AI_QA_ADMIN_PASSWORD",
    )
    assert redacted == "[REDACTED] used [REDACTED]; [REDACTED] used [REDACTED]"
