"""Resolve test credentials without putting their values in project configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values
from pydantic import SecretStr

from ai_qa_engineering.config import CredentialSettings


class MissingSecretError(ValueError):
    """Raised when a required credential environment variable is missing."""


@dataclass(frozen=True)
class ResolvedCredentials:
    username: SecretStr
    password: SecretStr


def resolve_credentials(
    settings: CredentialSettings,
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
