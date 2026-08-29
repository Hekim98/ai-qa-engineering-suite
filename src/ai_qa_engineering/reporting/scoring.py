"""Deterministic launch-readiness scoring and recommendation rules."""

from __future__ import annotations

from ai_qa_engineering.reporting.models import (
    AssessmentStatus,
    CategoryScore,
    FindingsDocument,
    LaunchReport,
    Recommendation,
    ScoreCategory,
    Severity,
)
from ai_qa_engineering.results import RunResult, RunStatus

WEIGHTS: dict[ScoreCategory, int] = {
    ScoreCategory.CORE_FLOWS: 40,
    ScoreCategory.RELIABILITY: 20,
    ScoreCategory.UX_CONTENT: 15,
    ScoreCategory.RESPONSIVE: 10,
    ScoreCategory.ACCESSIBILITY: 10,
    ScoreCategory.NETWORK: 5,
}

STATUS_FACTORS: dict[AssessmentStatus, float] = {
    AssessmentStatus.PASS: 1.0,
    AssessmentStatus.WARNING: 0.5,
    AssessmentStatus.FAIL: 0.0,
    AssessmentStatus.BLOCKED: 0.0,
}


def score_audit(document: FindingsDocument, run: RunResult) -> LaunchReport:
    category_scores = tuple(
        CategoryScore(
            category=assessment.category,
            status=assessment.status,
            weight=WEIGHTS[assessment.category],
            earned=WEIGHTS[assessment.category] * STATUS_FACTORS[assessment.status],
            rationale=assessment.rationale,
        )
        for assessment in document.report.assessments
    )
    readiness_findings = tuple(
        finding for finding in document.findings if not finding.is_detection_demonstration
    )
    detection_findings = tuple(
        finding for finding in document.findings if finding.is_detection_demonstration
    )
    blocked = (
        run.status is RunStatus.INCOMPLETE
        or any(item.status is AssessmentStatus.BLOCKED for item in document.report.assessments)
        or any(flow.status is AssessmentStatus.BLOCKED for flow in document.report.critical_flows)
    )
    if blocked:
        return LaunchReport(
            metadata=document.report,
            run_id=run.run_id,
            audit_status="incomplete",
            score=None,
            recommendation=Recommendation.INCOMPLETE,
            category_scores=category_scores,
            readiness_findings=readiness_findings,
            detection_findings=detection_findings,
        )

    score = round(sum(item.earned for item in category_scores))
    critical_finding = any(finding.severity is Severity.CRITICAL for finding in readiness_findings)
    failed_critical_flow = any(
        flow.status is AssessmentStatus.FAIL for flow in document.report.critical_flows
    )
    major_finding = any(finding.severity is Severity.MAJOR for finding in readiness_findings)

    if critical_finding or failed_critical_flow or score < 70:
        recommendation = Recommendation.DO_NOT_LAUNCH
    elif score < 90 or major_finding:
        recommendation = Recommendation.LAUNCH_WITH_CONDITIONS
    else:
        recommendation = Recommendation.READY_TO_LAUNCH

    return LaunchReport(
        metadata=document.report,
        run_id=run.run_id,
        audit_status="complete",
        score=score,
        recommendation=recommendation,
        category_scores=category_scores,
        readiness_findings=readiness_findings,
        detection_findings=detection_findings,
    )
