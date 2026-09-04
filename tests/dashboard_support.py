import json
from datetime import UTC, datetime
from pathlib import Path

import yaml

from ai_qa_engineering.audit_models import (
    AttemptSummary,
    AuditResult,
    AuditStatus,
    CandidateFinding,
    CandidateStatus,
    ProfileAuditSummary,
    SecretPreflight,
)
from ai_qa_engineering.results import RunStatus


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
        status=attempt_status,
        attempts=(attempt,),
        persistent_failures=(nodeid,) if with_candidate else (),
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
                    "files": [str(evidence_path)],
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
