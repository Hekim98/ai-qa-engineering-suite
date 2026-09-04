"""Resolve test credentials without putting their values in project configuration."""

from __future__ import annotations

import os
from base64 import b64encode
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, quote_plus

from dotenv import dotenv_values
from pydantic import SecretStr

from ai_qa_engineering.config import (
    APIAuthKind,
    APIAuthSettings,
    CredentialAccountSettings,
    CredentialSettings,
)


class MissingSecretError(ValueError):
    """Raised when a required credential environment variable is missing."""


@dataclass(frozen=True)
class ResolvedCredentials:
    username: SecretStr
    password: SecretStr


@dataclass(frozen=True)
class ResolvedAPIAuth:
    header_name: str
    header_value: SecretStr


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


def configured_api_secret_names(settings: APIAuthSettings | None) -> tuple[str, ...]:
    """Return the API authentication variable names without resolving their values."""
    if settings is None or settings.kind is APIAuthKind.NONE:
        return ()
    return tuple(
        name
        for name in (settings.token_env, settings.username_env, settings.password_env)
        if name is not None
    )


def _secret_value(variable_name: str, *, env_file: str | Path) -> str:
    file_values = dotenv_values(env_file)
    value = os.environ.get(variable_name) or file_values.get(variable_name)
    if not value:
        raise MissingSecretError(f"Required environment variable is missing: {variable_name}")
    return str(value)


def resolve_api_auth(
    settings: APIAuthSettings,
    *,
    env_file: str | Path = ".env",
) -> ResolvedAPIAuth | None:
    """Resolve one configured API authentication header entirely in memory."""
    if settings.kind is APIAuthKind.NONE:
        return None
    if settings.kind is APIAuthKind.BASIC:
        assert settings.username_env is not None and settings.password_env is not None
        username = _secret_value(settings.username_env, env_file=env_file)
        password = _secret_value(settings.password_env, env_file=env_file)
        encoded = b64encode(f"{username}:{password}".encode()).decode("ascii")
        return ResolvedAPIAuth("Authorization", SecretStr(f"Basic {encoded}"))
    assert settings.token_env is not None
    token = _secret_value(settings.token_env, env_file=env_file)
    if settings.kind is APIAuthKind.BEARER:
        return ResolvedAPIAuth("Authorization", SecretStr(f"Bearer {token}"))
    assert settings.header_name is not None
    return ResolvedAPIAuth(settings.header_name, SecretStr(token))


def available_secret_values(
    settings: CredentialSettings | None,
    *,
    env_file: str | Path = ".env",
    api_auth: APIAuthSettings | None = None,
) -> tuple[str, ...]:
    """Return configured values that are present, for in-memory redaction only."""
    file_values = dotenv_values(env_file)
    values: list[str] = []
    names = configured_secret_names(settings) if settings is not None else ()
    names += configured_api_secret_names(api_auth)
    for name in names:
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
