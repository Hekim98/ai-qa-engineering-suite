"""Validated contracts for local dashboard review decisions."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai_qa_engineering.reporting.models import (
    AssessmentStatus,
    CategoryAssessment,
    CriticalFlowResult,
    Recommendation,
    ScoreCategory,
    Severity,
)


class DashboardModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ReviewDecision(StrEnum):
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class ReviewSubmission(DashboardModel):
    candidate_id: str = Field(min_length=1, max_length=100)
    decision: ReviewDecision
    rationale: str = Field(min_length=3, max_length=2_000)
    severity: Severity | None = None
    category: ScoreCategory | None = None
    expected: str | None = Field(default=None, max_length=2_000)
    actual: str | None = Field(default=None, max_length=2_000)
    recommendation: str | None = Field(default=None, max_length=2_000)
    steps: tuple[str, ...] = Field(default=(), max_length=20)

    @model_validator(mode="after")
    def validate_confirmed_finding(self) -> ReviewSubmission:
        if self.decision is ReviewDecision.REJECTED:
            return self
        required_text = {
            "expected": self.expected,
            "actual": self.actual,
            "recommendation": self.recommendation,
        }
        missing = [name for name, value in required_text.items() if not value or not value.strip()]
        if self.severity is None:
            missing.append("severity")
        if self.category is None:
            missing.append("category")
        if not self.steps or any(not step.strip() for step in self.steps):
            missing.append("steps")
        if missing:
            raise ValueError("Confirmed findings require: " + ", ".join(sorted(set(missing))))
        return self


class CandidateReview(ReviewSubmission):
    reviewed_at: datetime


class ReviewDocument(DashboardModel):
    schema_version: int = 1
    audit_id: str
    updated_at: datetime
    reviews: tuple[CandidateReview, ...] = ()


class ReportWorkspaceSubmission(DashboardModel):
    title: str = Field(min_length=3, max_length=200)
    executive_summary: str = Field(min_length=20, max_length=5_000)
    assessments: tuple[CategoryAssessment, ...]
    critical_flows: tuple[CriticalFlowResult, ...] = Field(min_length=1, max_length=100)
    limitations: tuple[str, ...] = Field(min_length=1, max_length=50)
    allowlisted_observations: tuple[str, ...] = Field(default=(), max_length=100)

    @model_validator(mode="after")
    def validate_complete_workspace(self) -> ReportWorkspaceSubmission:
        categories = [assessment.category for assessment in self.assessments]
        if set(categories) != set(ScoreCategory) or len(categories) != len(ScoreCategory):
            raise ValueError("Assessments must contain each score category exactly once")
        flow_ids = [flow.id for flow in self.critical_flows]
        if len(flow_ids) != len(set(flow_ids)):
            raise ValueError("Critical flow IDs must be unique")
        collections = {
            "limitations": self.limitations,
            "allowlisted observations": self.allowlisted_observations,
        }
        for name, values in collections.items():
            if any(not value.strip() for value in values):
                raise ValueError(f"{name.capitalize()} cannot contain blank values")
        return self


class ReportWorkspaceDocument(ReportWorkspaceSubmission):
    schema_version: int = 1
    audit_id: str
    updated_at: datetime


class VerificationCheck(DashboardModel):
    name: str = Field(min_length=1, max_length=100)
    passed: bool
    detail: str = Field(min_length=1, max_length=2_000)


class ReportVerificationStatus(StrEnum):
    AWAITING_VISUAL_REVIEW = "awaiting-visual-review"
    VERIFIED = "verified"


class ReportVerificationDocument(DashboardModel):
    schema_version: int = 1
    audit_id: str
    input_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    generated_at: datetime
    status: ReportVerificationStatus
    score: int | None = Field(default=None, ge=0, le=100)
    recommendation: Recommendation
    html_path: Path
    pdf_path: Path
    page_images: tuple[Path, ...] = Field(min_length=1)
    page_count: int = Field(ge=1)
    automated_checks: tuple[VerificationCheck, ...] = Field(min_length=1)
    visual_reviewed_at: datetime | None = None
    visual_review_rationale: str | None = Field(default=None, max_length=2_000)

    @model_validator(mode="after")
    def validate_visual_review(self) -> ReportVerificationDocument:
        if self.status is ReportVerificationStatus.VERIFIED:
            if self.visual_reviewed_at is None or not self.visual_review_rationale:
                raise ValueError("Verified reports require a visual review timestamp and rationale")
        return self


class VisualReviewSubmission(DashboardModel):
    rationale: str = Field(min_length=3, max_length=2_000)


class WorkspaceReadiness(StrEnum):
    MISSING = "missing"
    BLOCKED = "blocked"
    READY = "ready"
    STALE = "stale"
    AWAITING_VISUAL_REVIEW = "awaiting-visual-review"
    VERIFIED = "verified"


def default_assessments() -> tuple[dict[str, str], ...]:
    """Return neutral, intentionally incomplete values for the browser form."""
    return tuple(
        {"category": category.value, "status": "", "rationale": ""} for category in ScoreCategory
    )


def blocked_assessment_statuses() -> tuple[AssessmentStatus, ...]:
    """Keep the report-workspace status vocabulary in one discoverable place."""
    return tuple(AssessmentStatus)
