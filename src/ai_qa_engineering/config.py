"""Typed project configuration loading and validation."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any, Self

import yaml
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator, model_validator


class ConfigError(ValueError):
    """Raised when a project configuration cannot be loaded or validated."""


class BrowserEngine(StrEnum):
    CHROMIUM = "chromium"
    FIREFOX = "firefox"
    WEBKIT = "webkit"


class SuiteLevel(StrEnum):
    FULL = "full"
    SMOKE = "smoke"
    DETECTION_DEMO = "detection_demo"


class EvidencePolicy(StrEnum):
    ALWAYS = "always"
    ON_FAILURE = "on-failure"
    OFF = "off"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _safe_relative_path(value: Path, field_name: str) -> Path:
    if value.is_absolute() or ".." in value.parts:
        raise ValueError(f"{field_name} must be a safe path relative to the repository root")
    if str(value) in {"", "."}:
        raise ValueError(f"{field_name} must name a directory or file")
    return value


class ProjectSettings(StrictModel):
    name: str = Field(min_length=1)
    base_url: AnyHttpUrl
    environment: str = Field(min_length=1)
    tests_path: Path

    @field_validator("tests_path")
    @classmethod
    def validate_tests_path(cls, value: Path) -> Path:
        return _safe_relative_path(value, "project.tests_path")


class CredentialSettings(StrictModel):
    username_env: str = Field(min_length=1, pattern=r"^[A-Z][A-Z0-9_]*$")
    password_env: str = Field(min_length=1, pattern=r"^[A-Z][A-Z0-9_]*$")


class ViewportSettings(StrictModel):
    width: int = Field(gt=0, le=7680)
    height: int = Field(gt=0, le=4320)


class BrowserProfile(StrictModel):
    engine: BrowserEngine
    suite: SuiteLevel
    viewport: ViewportSettings
    mobile: bool = False


class BrowserSettings(StrictModel):
    profiles: dict[str, BrowserProfile] = Field(min_length=1)

    @field_validator("profiles")
    @classmethod
    def validate_profile_names(cls, value: dict[str, BrowserProfile]) -> dict[str, BrowserProfile]:
        for name in value:
            if not name.replace("-", "_").isidentifier():
                raise ValueError(
                    "browser profile names may contain only letters, numbers, "
                    "underscores, and hyphens"
                )
        return value


class ArtifactSettings(StrictModel):
    root_dir: Path
    screenshot: EvidencePolicy = EvidencePolicy.ON_FAILURE
    video: EvidencePolicy = EvidencePolicy.ON_FAILURE
    trace: EvidencePolicy = EvidencePolicy.ON_FAILURE

    @field_validator("root_dir")
    @classmethod
    def validate_root_dir(cls, value: Path) -> Path:
        return _safe_relative_path(value, "artifacts.root_dir")


class NetworkSettings(StrictModel):
    capture_console_errors: bool = True
    capture_failed_requests: bool = True
    allowlist: tuple[str, ...] = ()


class CriticalFlow(StrictModel):
    id: str = Field(min_length=1, pattern=r"^[A-Z][A-Z0-9_-]*$")
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)


class QAConfig(StrictModel):
    project: ProjectSettings
    credentials: CredentialSettings
    browser: BrowserSettings
    artifacts: ArtifactSettings
    network: NetworkSettings = NetworkSettings()
    critical_flows: tuple[CriticalFlow, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_flow_ids(self) -> Self:
        identifiers = [flow.id for flow in self.critical_flows]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("critical flow IDs must be unique")
        return self


def load_config(path: str | Path) -> QAConfig:
    """Load a YAML file and return an immutable, validated project configuration."""
    config_path = Path(path)
    if not config_path.is_file():
        raise ConfigError(f"Configuration file not found: {config_path}")

    try:
        raw: Any = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ConfigError(f"Could not read configuration {config_path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError("Configuration root must be a YAML mapping")

    try:
        return QAConfig.model_validate(raw)
    except ValueError as exc:
        raise ConfigError(f"Invalid configuration {config_path}: {exc}") from exc
