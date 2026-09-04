import json
from datetime import UTC, datetime
from pathlib import Path

import yaml

from ai_qa_engineering.audit_models import (
    AttemptSummary,
    AuditedAPICheck,
    AuditedCriticalFlow,
    AuditResult,
    AuditStatus,
    CandidateFinding,
    CandidateStatus,
    ProfileAuditSummary,
    SecretPreflight,
)
from ai_qa_engineering.dashboard_models import ReportWorkspaceSubmission
from ai_qa_engineering.reporting.models import (
    AssessmentStatus,
    CategoryAssessment,
    CriticalFlowResult,
    ScoreCategory,
)
from ai_qa_engineering.results import APICheckOutcome, RunStatus


def write_dashboard_fixture(
    root: Path,
    *,
    with_candidate: bool = True,
    status: AuditStatus | None = None,
) -> AuditResult:
    config_root = root / "configs"
    config_root.mkdir(parents=True, exist_ok=True)
    source = Path("configs/example.yaml").read_text(encoding="utf-8")
    (config_root / "example.yaml").write_text(source, encoding="utf-8")

    audit_id = "20260904T120000Z-dashboard-fixture-audit"
    directory = root / "artifacts/audits" / audit_id
    run_directory = directory / "profiles/run-one"
    report_directory = directory / "reports"
    run_directory.mkdir(parents=True)
    report_directory.mkdir()
    run_json = run_directory / "run.json"
    run_json.write_text('{"fixture": true}', encoding="utf-8")
    evidence_path = run_json.relative_to(root)
    api_evidence = run_directory / "api/check.json"
    api_evidence.parent.mkdir()
    api_evidence.write_text('{"authorization":"[REDACTED]"}', encoding="utf-8")
    api_evidence_path = api_evidence.relative_to(root)
    nodeid = "tests/example.py::test_checkout"
    candidates = (
        (
            CandidateFinding(
                id="AUTO-001",
                title="Checkout",
                status=CandidateStatus.CANDIDATE,
                test=nodeid,
                profiles=("desktop-chromium",),
                browsers=("chromium",),
                occurrences=1,
                evidence=(evidence_path,),
            ),
        )
        if with_candidate
        else ()
    )
    attempt_status = RunStatus.FAILED if with_candidate else RunStatus.PASSED
    attempt = AttemptSummary(
        attempt=1,
        run_id="run-one",
        run_directory=run_directory.relative_to(root),
        status=attempt_status,
        test_count=1,
        passed=0 if with_candidate else 1,
        failed=1 if with_candidate else 0,
        skipped=0,
        errors=0,
    )
    profile = ProfileAuditSummary(
        profile="desktop-chromium",
        browser="chromium",
        device="Desktop",
        suite="full",
        status=attempt_status,
        attempts=(attempt,),
        persistent_failures=(nodeid,) if with_candidate else (),
        api_checks=1,
        api_passed=1,
    )
    resolved_status = status or (AuditStatus.NEEDS_REVIEW if with_candidate else AuditStatus.PASSED)
    audit = AuditResult(
        audit_id=audit_id,
        project="dashboard-fixture",
        environment="local",
        target="https://example.test",
        status=resolved_status,
        started_at=datetime(2026, 9, 4, 12, tzinfo=UTC),
        finished_at=datetime(2026, 9, 4, 12, 1, tzinfo=UTC),
        profiles=(profile,),
        critical_flows=(
            AuditedCriticalFlow(
                id="FLOW-001",
                name="Complete checkout",
                description="A customer can complete the primary checkout journey.",
            ),
        ),
        api_checks=(
            AuditedAPICheck(
                name="Read checkout",
                test=nodeid,
                profile="desktop-chromium",
                method="GET",
                path="/api/checkout",
                expected_statuses=(200,),
                actual_status=200,
                latency_ms=12.5,
                latency_budget_ms=500,
                response_schema="CheckoutResponse",
                schema_valid=True,
                outcome=APICheckOutcome.PASSED,
                evidence=api_evidence_path,
            ),
        ),
        candidate_findings=candidates,
        total_tests=1,
        passed_tests=0 if with_candidate else 1,
        persistent_failures=1 if with_candidate else 0,
        flaky_tests=0,
        secret_preflight=SecretPreflight(
            configured=False,
            screenshot_masking_configured=False,
        ),
    )
    (directory / "audit.json").write_text(audit.model_dump_json(indent=2), encoding="utf-8")
    (directory / "evidence-index.json").write_text(
        json.dumps(
            [
                {
                    "profile": "desktop-chromium",
                    "run_id": "run-one",
                    "files": [str(evidence_path), str(api_evidence_path)],
                }
            ]
        ),
        encoding="utf-8",
    )
    (directory / "candidate-findings.yaml").write_text(
        yaml.safe_dump({"findings": [item.model_dump(mode="json") for item in candidates]}),
        encoding="utf-8",
    )
    (report_directory / "draft-audit-report.html").write_text(
        "<h1>Fixture report</h1>", encoding="utf-8"
    )
    (report_directory / "draft-audit-report.pdf").write_bytes(b"%PDF-fixture")
    return audit


def report_workspace_submission(
    *,
    title: str = "Dashboard Fixture Launch Readiness Report",
) -> ReportWorkspaceSubmission:
    return ReportWorkspaceSubmission(
        title=title,
        executive_summary=(
            "The verified local audit supports a launch decision based on the reviewed evidence."
        ),
        assessments=tuple(
            CategoryAssessment(
                category=category,
                status=AssessmentStatus.PASS,
                rationale=f"Verified evidence supports {category.value}.",
            )
            for category in ScoreCategory
        ),
        critical_flows=(
            CriticalFlowResult(
                id="FLOW-001",
                name="Complete checkout",
                status=AssessmentStatus.PASS,
                evidence="The primary automated journey passed in Chromium.",
            ),
        ),
        limitations=("The fixture covers one controlled browser profile.",),
    )
