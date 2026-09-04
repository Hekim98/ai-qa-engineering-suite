"""Resolve test credentials without putting their values in project configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, quote_plus

from dotenv import dotenv_values
from pydantic import SecretStr

from ai_qa_engineering.config import CredentialAccountSettings, CredentialSettings


class MissingSecretError(ValueError):
    """Raised when a required credential environment variable is missing."""


@dataclass(frozen=True)
class ResolvedCredentials:
    username: SecretStr
    password: SecretStr


def resolve_credentials(
    settings: CredentialAccountSettings,
    *,
    env_file: str | Path = ".env",
) -> ResolvedCredentials:
    """Resolve credentials, preferring process variables over a local ``.env`` file."""
    file_values = dotenv_values(env_file)

    def require(variable_name: str) -> SecretStr:
        value = os.environ.get(variable_name) or file_values.get(variable_name)
        if not value:
            raise MissingSecretError(f"Required environment variable is missing: {variable_name}")
        return SecretStr(value)

    return ResolvedCredentials(
        username=require(settings.username_env),
        password=require(settings.password_env),
    )


def resolve_accounts(
    settings: CredentialSettings,
    *,
    env_file: str | Path = ".env",
) -> dict[str, ResolvedCredentials]:
    """Resolve the default account and every named role from the same secret sources."""
    accounts = {"default": resolve_credentials(settings, env_file=env_file)}
    accounts.update(
        {
            name: resolve_credentials(account, env_file=env_file)
            for name, account in settings.accounts.items()
        }
    )
    return accounts


def configured_secret_names(settings: CredentialSettings) -> tuple[str, ...]:
    """Return only safe variable names for audit metadata and preflight summaries."""
    pairs = [(settings.username_env, settings.password_env)]
    pairs.extend(
        (account.username_env, account.password_env) for account in settings.accounts.values()
    )
    return tuple(name for pair in pairs for name in pair)


def available_secret_values(
    settings: CredentialSettings | None,
    *,
    env_file: str | Path = ".env",
) -> tuple[str, ...]:
    """Return configured values that are present, for in-memory redaction only."""
    if settings is None:
        return ()
    file_values = dotenv_values(env_file)
    values: list[str] = []
    for name in configured_secret_names(settings):
        value = os.environ.get(name) or file_values.get(name)
        if value:
            values.extend((value, quote(value, safe=""), quote_plus(value)))
    return tuple(dict.fromkeys(values))


def redact_text(value: str, secrets: tuple[str, ...]) -> str:
    """Replace configured secret values without ever persisting a redaction dictionary."""
    redacted = value
    for secret in sorted(secrets, key=len, reverse=True):
        redacted = redacted.replace(secret, "[REDACTED]")
    return redacted
