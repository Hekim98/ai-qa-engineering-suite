"""Strict data contracts shared by HTML and PDF reports."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from pathlib import Path

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, model_validator


class ReportModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class Severity(StrEnum):
    CRITICAL = "Critical"
    MAJOR = "Major"
    MINOR = "Minor"


class AssessmentStatus(StrEnum):
    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"


class ScoreCategory(StrEnum):
    CORE_FLOWS = "core-flows"
    RELIABILITY = "reliability-error-handling"
    UX_CONTENT = "ux-content"
    RESPONSIVE = "responsive"
    ACCESSIBILITY = "accessibility-smoke"
    NETWORK = "network-health"


class Recommendation(StrEnum):
    DO_NOT_LAUNCH = "DO NOT LAUNCH"
    LAUNCH_WITH_CONDITIONS = "LAUNCH WITH CONDITIONS"
    READY_TO_LAUNCH = "READY TO LAUNCH"
    INCOMPLETE = "INCOMPLETE"


class Finding(ReportModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    severity: Severity
    category: str = Field(min_length=1)
    source: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    browser_device: str = Field(alias="browser/device", min_length=1)
    steps: tuple[str, ...] = Field(min_length=1)
    expected: str = Field(min_length=1)
    actual: str = Field(min_length=1)
    evidence: tuple[Path, ...] = Field(min_length=1)
    recommendation: str = Field(min_length=1)
    status: str = Field(min_length=1)

    @property
    def is_detection_demonstration(self) -> bool:
        return self.source == "detection-demonstration"


class CategoryAssessment(ReportModel):
    category: ScoreCategory
    status: AssessmentStatus
    rationale: str = Field(min_length=1)


class CriticalFlowResult(ReportModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    status: AssessmentStatus
    evidence: str = Field(min_length=1)


class BrowserCoverage(ReportModel):
    profile: str = Field(min_length=1)
    browser: str = Field(min_length=1)
    device: str = Field(min_length=1)
    suite: str = Field(min_length=1)
    result: str = Field(min_length=1)


class APICoverage(ReportModel):
    name: str = Field(min_length=1)
    profile: str = Field(min_length=1)
    method: str = Field(min_length=1)
    path: str = Field(min_length=1)
    status: str = Field(min_length=1)
    latency_ms: float | None = None
    latency_budget_ms: int = Field(gt=0)
    response_schema: str | None = None


class ReportMetadata(ReportModel):
    title: str = Field(min_length=1)
    project: str = Field(min_length=1)
    target: AnyHttpUrl
    audit_date: date
    executive_summary: str = Field(min_length=1)
    assessments: tuple[CategoryAssessment, ...]
    critical_flows: tuple[CriticalFlowResult, ...] = Field(min_length=1)
    browser_coverage: tuple[BrowserCoverage, ...] = Field(min_length=1)
    api_coverage: tuple[APICoverage, ...] = ()
    limitations: tuple[str, ...] = Field(min_length=1)
    allowlisted_observations: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_score_categories(self) -> ReportMetadata:
        categories = [assessment.category for assessment in self.assessments]
        required = set(ScoreCategory)
        if set(categories) != required or len(categories) != len(required):
            raise ValueError("assessments must contain each score category exactly once")
        return self


class FindingsDocument(ReportModel):
    report: ReportMetadata
    findings: tuple[Finding, ...]


class CategoryScore(ReportModel):
    category: ScoreCategory
    status: AssessmentStatus
    weight: int
    earned: float
    rationale: str


class LaunchReport(ReportModel):
    metadata: ReportMetadata
    run_id: str
    audit_status: str
    score: int | None
    recommendation: Recommendation
    category_scores: tuple[CategoryScore, ...]
    readiness_findings: tuple[Finding, ...]
    detection_findings: tuple[Finding, ...]
