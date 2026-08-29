from datetime import UTC, datetime
from pathlib import Path

import pytest

from ai_qa_engineering.reporting.models import (
    AssessmentStatus,
    BrowserCoverage,
    CategoryAssessment,
    CriticalFlowResult,
    Finding,
    FindingsDocument,
    Recommendation,
    ReportMetadata,
    ScoreCategory,
    Severity,
)
from ai_qa_engineering.reporting.scoring import score_audit
from ai_qa_engineering.results import RunResult, RunStatus


def _assessments(**overrides: AssessmentStatus) -> tuple[CategoryAssessment, ...]:
    return tuple(
        CategoryAssessment(
            category=category,
            status=overrides.get(category.value, AssessmentStatus.PASS),
            rationale=f"Verified {category.value}",
        )
        for category in ScoreCategory
    )


def _document(
    *,
    assessments: tuple[CategoryAssessment, ...] | None = None,
    findings: tuple[Finding, ...] = (),
    flow_status: AssessmentStatus = AssessmentStatus.PASS,
) -> FindingsDocument:
    return FindingsDocument(
        report=ReportMetadata(
            title="Demo Launch Report",
            project="demo",
            target="https://example.com",
            audit_date="2026-08-29",
            executive_summary="Verified audit summary.",
            assessments=assessments or _assessments(),
            critical_flows=(
                CriticalFlowResult(
                    id="FLOW-001",
                    name="Core flow",
                    status=flow_status,
                    evidence="Automated journey",
                ),
            ),
            browser_coverage=(
                BrowserCoverage(
                    profile="desktop-chromium",
                    browser="Chromium",
                    device="Desktop",
                    suite="full",
                    result="passed",
                ),
            ),
            limitations=("Demo only",),
        ),
        findings=findings,
    )


def _run(status: RunStatus = RunStatus.PASSED) -> RunResult:
    return RunResult(
        run_id="run-1",
        project="demo",
        environment="test",
        profile="desktop-chromium",
        browser="chromium",
        status=status,
        started_at=datetime(2026, 8, 29, tzinfo=UTC),
        finished_at=datetime(2026, 8, 29, tzinfo=UTC),
        pytest_exit_code=0,
        tests=(),
    )


def _finding(*, severity: Severity, source: str = "automated") -> Finding:
    return Finding.model_validate(
        {
            "id": "F-001",
            "title": "Verified issue",
            "severity": severity,
            "category": "accessibility-smoke",
            "source": source,
            "environment": "test",
            "browser/device": "Chromium desktop",
            "steps": ["Open the page"],
            "expected": "Expected state",
            "actual": "Actual state",
            "evidence": ["evidence.png"],
            "recommendation": "Fix the issue",
            "status": "verified",
        }
    )


@pytest.mark.unit
def test_score_uses_weights_and_excludes_detection_demonstration() -> None:
    assessments = _assessments(
        responsive=AssessmentStatus.WARNING,
        **{"accessibility-smoke": AssessmentStatus.FAIL, "network-health": AssessmentStatus.FAIL},
    )
    document = _document(
        assessments=assessments,
        findings=(
            _finding(severity=Severity.MAJOR),
            _finding(severity=Severity.MAJOR, source="detection-demonstration"),
        ),
    )

    report = score_audit(document, _run(RunStatus.FAILED))

    assert report.score == 80
    assert report.recommendation is Recommendation.LAUNCH_WITH_CONDITIONS
    assert len(report.readiness_findings) == 1
    assert len(report.detection_findings) == 1


@pytest.mark.unit
@pytest.mark.parametrize(
    ("document", "run", "recommendation", "score"),
    [
        (
            _document(findings=(_finding(severity=Severity.CRITICAL),)),
            _run(),
            Recommendation.DO_NOT_LAUNCH,
            100,
        ),
        (
            _document(flow_status=AssessmentStatus.FAIL),
            _run(),
            Recommendation.DO_NOT_LAUNCH,
            100,
        ),
        (
            _document(assessments=_assessments(**{"core-flows": AssessmentStatus.BLOCKED})),
            _run(),
            Recommendation.INCOMPLETE,
            None,
        ),
        (
            _document(),
            _run(RunStatus.INCOMPLETE),
            Recommendation.INCOMPLETE,
            None,
        ),
    ],
)
def test_decision_rules(
    document: FindingsDocument,
    run: RunResult,
    recommendation: Recommendation,
    score: int | None,
) -> None:
    report = score_audit(document, run)

    assert report.recommendation is recommendation
    assert report.score == score


@pytest.mark.unit
def test_report_metadata_requires_each_category_once() -> None:
    with pytest.raises(ValueError, match="each score category"):
        _document(assessments=_assessments()[:-1])


@pytest.mark.unit
def test_finding_browser_device_alias_round_trips() -> None:
    finding = _finding(severity=Severity.MINOR)

    assert finding.browser_device == "Chromium desktop"
    assert finding.model_dump(by_alias=True)["browser/device"] == "Chromium desktop"
    assert finding.evidence == (Path("evidence.png"),)
