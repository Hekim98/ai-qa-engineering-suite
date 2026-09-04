"""Validated contracts for local dashboard review decisions."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai_qa_engineering.reporting.models import ScoreCategory, Severity


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
