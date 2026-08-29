from pathlib import Path

import pytest

from ai_qa_engineering.config import CredentialSettings
from ai_qa_engineering.secrets import MissingSecretError, resolve_credentials

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
