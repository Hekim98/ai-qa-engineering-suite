"""Structured results written by each QA run."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class ResultModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TestOutcome(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


class RunStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    INCOMPLETE = "incomplete"


class ConsoleRecord(ResultModel):
    level: str
    text: str
    url: str | None = None


class NetworkRecord(ResultModel):
    url: str
    method: str
    reason: str
    status: int | None = None


class TestResult(ResultModel):
    nodeid: str
    outcome: TestOutcome
    duration_seconds: float
    error: str | None = None


class RunResult(ResultModel):
    schema_version: int = 1
    run_id: str
    project: str
    environment: str
    profile: str
    browser: str
    status: RunStatus
    started_at: datetime
    finished_at: datetime
    pytest_exit_code: int
    tests: tuple[TestResult, ...]
    console_errors: tuple[ConsoleRecord, ...] = ()
    failed_requests: tuple[NetworkRecord, ...] = ()
    artifacts: tuple[str, ...] = ()
    incomplete_reason: str | None = None
