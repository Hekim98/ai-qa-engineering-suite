"""Validated contracts for a multi-profile orchestrated audit."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from ai_qa_engineering.results import APICheckOutcome, RunStatus


class AuditModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AuditStatus(StrEnum):
    PASSED = "passed"
    NEEDS_REVIEW = "needs-review"
    INCOMPLETE = "incomplete"


class CandidateStatus(StrEnum):
    CANDIDATE = "candidate"
    FLAKY = "flaky"


class AttemptSummary(AuditModel):
    attempt: int = Field(ge=1, le=2)
    run_id: str
    run_directory: Path
    status: RunStatus
    test_count: int = Field(ge=0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    skipped: int = Field(ge=0)
    errors: int = Field(ge=0)
    incomplete_reason: str | None = None


class ProfileAuditSummary(AuditModel):
    profile: str
    browser: str
    device: str | None = None
    suite: str | None = None
    status: RunStatus
    attempts: tuple[AttemptSummary, ...] = Field(min_length=1, max_length=2)
    persistent_failures: tuple[str, ...] = ()
    flaky_tests: tuple[str, ...] = ()
    api_checks: int = Field(default=0, ge=0)
    api_passed: int = Field(default=0, ge=0)
    api_failed: int = Field(default=0, ge=0)


class CandidateFinding(AuditModel):
    id: str
    title: str
    status: CandidateStatus
    test: str
    profiles: tuple[str, ...] = Field(min_length=1)
    browsers: tuple[str, ...] = Field(min_length=1)
    occurrences: int = Field(ge=1)
    evidence: tuple[Path, ...] = Field(min_length=1)
    human_verification_required: bool = True


class SecretPreflight(AuditModel):
    configured: bool
    account_names: tuple[str, ...] = ()
    required_environment_variables: tuple[str, ...] = ()
    screenshot_masking_configured: bool
    api_authentication_configured: bool = False


class AuditedCriticalFlow(AuditModel):
    id: str
    name: str
    description: str


class AuditedAPICheck(AuditModel):
    name: str
    test: str
    profile: str
    method: str
    path: str
    expected_statuses: tuple[int, ...]
    actual_status: int | None = None
    latency_ms: float | None = None
    latency_budget_ms: int
    response_schema: str | None = None
    schema_valid: bool | None = None
    outcome: APICheckOutcome
    evidence: Path
    failure_reason: str | None = None


class AuditResult(AuditModel):
    schema_version: int = 3
    audit_id: str
    project: str
    environment: str
    target: str
    status: AuditStatus
    started_at: datetime
    finished_at: datetime
    profiles: tuple[ProfileAuditSummary, ...]
    critical_flows: tuple[AuditedCriticalFlow, ...] = ()
    api_checks: tuple[AuditedAPICheck, ...] = ()
    candidate_findings: tuple[CandidateFinding, ...] = ()
    total_tests: int = Field(ge=0)
    passed_tests: int = Field(ge=0)
    persistent_failures: int = Field(ge=0)
    flaky_tests: int = Field(ge=0)
    secret_preflight: SecretPreflight
    score: None = None
    recommendation: None = None
    verification_note: str = (
        "Draft automation output only. Human verification is required before scoring or "
        "publishing a launch recommendation."
    )
