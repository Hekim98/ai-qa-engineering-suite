import time
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from typing import cast

import pytest

from ai_qa_engineering.dashboard import (
    DashboardConflictError,
    DashboardNotFoundError,
    DashboardService,
)
from ai_qa_engineering.dashboard_models import ReviewSubmission, VisualReviewSubmission
from ai_qa_engineering.orchestration import AuditOutputs
from ai_qa_engineering.reporting.verification import VerificationResult
from tests.dashboard_support import report_workspace_submission, write_dashboard_fixture


def _wait_for_job(service: DashboardService, status: str) -> dict[str, object]:
    for _ in range(100):
        job = service.list_jobs()[0]
        if job["status"] == status:
            return job
        time.sleep(0.01)
    raise AssertionError(f"Dashboard job did not reach {status}")


@pytest.mark.unit
def test_dashboard_lists_configs_audits_evidence_and_report_gate(tmp_path: Path) -> None:
    audit = write_dashboard_fixture(tmp_path)
    service = DashboardService(tmp_path)

    state = service.state()
    detail = service.audit_detail(audit.audit_id)

    configurations = cast(list[dict[str, object]], state["configurations"])
    audits = cast(list[dict[str, object]], state["audits"])
    assert configurations[0]["path"] == "configs/example.yaml"
    assert configurations[0]["requires_credentials"] is True
    assert audits[0]["project"] == "dashboard-fixture"
    assert detail["review"] == {
        "total": 1,
        "confirmed": 0,
        "rejected": 0,
        "pending": 1,
        "complete": False,
        "report_gate": "blocked",
        "report_gate_reason": "Every candidate finding must be confirmed or rejected.",
    }
    evidence = cast(list[dict[str, object]], detail["evidence"])
    files = cast(list[dict[str, str]], evidence[0]["files"])
    path, content_type = service.open_evidence(audit.audit_id, files[0]["path"])
    assert path.name == "run.json"
    assert content_type == "text/plain; charset=utf-8"
    audit_payload = cast(dict[str, object], detail["audit"])
    api_checks = cast(list[dict[str, object]], audit_payload["api_checks"])
    assert api_checks[0]["response_schema"] == "CheckoutResponse"
    assert str(api_checks[0]["evidence_url"]).startswith("/api/evidence/")

    with pytest.raises(DashboardNotFoundError, match="Evidence file not found"):
        service.open_evidence(audit.audit_id, "../../.env")
    with pytest.raises(DashboardNotFoundError, match="Audit not found"):
        service.audit_detail("../outside")


@pytest.mark.unit
def test_dashboard_saves_review_decisions_atomically_and_opens_gate(tmp_path: Path) -> None:
    audit = write_dashboard_fixture(tmp_path)
    service = DashboardService(tmp_path)
    rejected = ReviewSubmission.model_validate(
        {
            "candidate_id": "AUTO-001",
            "decision": "rejected",
            "rationale": "The seeded negative scenario is expected.",
        }
    )

    result = service.save_review(audit.audit_id, rejected)

    summary = cast(dict[str, object], result["summary"])
    assert summary["report_gate"] == "open"
    review_path = tmp_path / "artifacts/audits" / audit.audit_id / "review-decisions.json"
    assert review_path.is_file()
    assert not review_path.with_suffix(".json.tmp").exists()

    confirmed = ReviewSubmission.model_validate(
        {
            "candidate_id": "AUTO-001",
            "decision": "confirmed",
            "rationale": "Reproduced in the supported browser.",
            "severity": "Major",
            "category": "core-flows",
            "steps": ["Open checkout", "Submit an order"],
            "expected": "The order completes.",
            "actual": "The request fails.",
            "recommendation": "Repair checkout before launch.",
        }
    )
    service.save_review(audit.audit_id, confirmed)
    detail = service.audit_detail(audit.audit_id)
    candidates = cast(list[dict[str, object]], detail["candidates"])
    saved = cast(dict[str, object], candidates[0]["review"])
    assert saved["decision"] == "confirmed"

    with pytest.raises(DashboardNotFoundError, match="Candidate not found"):
        service.save_review(
            audit.audit_id,
            rejected.model_copy(update={"candidate_id": "AUTO-999"}),
        )


@pytest.mark.unit
def test_dashboard_runs_one_background_audit_at_a_time(tmp_path: Path) -> None:
    audit = write_dashboard_fixture(tmp_path, with_candidate=False)
    release = Event()

    def fake_runner(*_args: object, **_kwargs: object) -> AuditOutputs:
        release.wait(timeout=2)
        return cast(AuditOutputs, SimpleNamespace(audit=audit))

    service = DashboardService(tmp_path, audit_runner=fake_runner)
    started = service.start_audit("configs/example.yaml", ["desktop-chromium"])

    assert started["status"] in {"queued", "running"}
    with pytest.raises(DashboardConflictError, match="already running"):
        service.start_audit("configs/example.yaml", ["desktop-chromium"])

    release.set()
    completed = _wait_for_job(service, "completed")
    assert completed["audit_id"] == audit.audit_id


@pytest.mark.unit
def test_dashboard_redacts_secrets_from_background_errors(tmp_path: Path) -> None:
    write_dashboard_fixture(tmp_path, with_candidate=False)
    (tmp_path / ".env").write_text(
        "AI_QA_TEST_USER_EMAIL=private@example.test\nAI_QA_TEST_USER_PASSWORD=private-pass\n",
        encoding="utf-8",
    )

    def fail(*_args: object, **_kwargs: object) -> AuditOutputs:
        raise RuntimeError("private@example.test used private-pass")

    service = DashboardService(tmp_path, audit_runner=fail)
    service.start_audit("configs/example.yaml", ["desktop-chromium"])
    failed = _wait_for_job(service, "failed")

    assert failed["error"] == "[REDACTED] used [REDACTED]"


@pytest.mark.unit
def test_report_workspace_generates_tracks_and_visually_approves_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audit = write_dashboard_fixture(tmp_path)
    service = DashboardService(tmp_path)
    initial = cast(dict[str, object], service.audit_detail(audit.audit_id)["report_workspace"])
    assert initial["status"] == "blocked"

    service.save_review(
        audit.audit_id,
        ReviewSubmission.model_validate(
            {
                "candidate_id": "AUTO-001",
                "decision": "confirmed",
                "rationale": "Reproduced against the controlled checkout fixture.",
                "severity": "Major",
                "category": "core-flows",
                "steps": ["Open checkout", "Submit the order"],
                "expected": "The order completes.",
                "actual": "The request fails.",
                "recommendation": "Repair checkout before launch.",
            }
        ),
    )
    missing = cast(dict[str, object], service.audit_detail(audit.audit_id)["report_workspace"])
    assert missing["status"] == "missing"
    saved = service.save_report_workspace(audit.audit_id, report_workspace_submission())
    assert saved["status"] == "ready"

    def fake_render(*_args: object, **kwargs: object) -> None:
        Path(cast(str | Path, kwargs["html_path"])).write_text(
            "<!doctype html><title>fixture</title>", encoding="utf-8"
        )
        Path(cast(str | Path, kwargs["pdf_path"])).write_bytes(b"%PDF-fixture")

    def fake_verify(
        _report: object,
        _html_path: Path,
        _pdf_path: Path,
        *,
        render_directory: Path,
    ) -> VerificationResult:
        render_directory.mkdir(parents=True)
        page = render_directory / "page-1.png"
        page.write_bytes(b"fixture-image")
        return VerificationResult(
            page_count=1,
            page_images=(page,),
            checks=(("Rendered pages", "One page rendered."),),
        )

    monkeypatch.setattr("ai_qa_engineering.dashboard.render_report_outputs", fake_render)
    monkeypatch.setattr("ai_qa_engineering.dashboard.verify_report_outputs", fake_verify)

    generated = service.generate_verified_report(audit.audit_id)
    assert generated["status"] == "awaiting-visual-review"
    verification = cast(dict[str, object], generated["verification"])
    assert verification["score"] == 100
    assert verification["recommendation"] == "LAUNCH WITH CONDITIONS"
    directory = tmp_path / "artifacts/audits" / audit.audit_id
    assert (directory / "verified-report-inputs.yaml").is_file()
    assert "AUTO-001" in (directory / "verified-report-inputs.yaml").read_text(encoding="utf-8")

    approved = service.approve_visual_report(
        audit.audit_id,
        VisualReviewSubmission(rationale="Every rendered page is readable and unclipped."),
    )
    assert approved["status"] == "verified"

    changed = report_workspace_submission(title="Changed Launch Readiness Report")
    stale = service.save_report_workspace(audit.audit_id, changed)
    assert stale["status"] == "stale"
    assert stale["can_approve_visual"] is False


@pytest.mark.unit
def test_report_workspace_rejects_mismatched_flow_definitions(tmp_path: Path) -> None:
    audit = write_dashboard_fixture(tmp_path, with_candidate=False)
    service = DashboardService(tmp_path)
    workspace = report_workspace_submission()
    incorrect_flow = workspace.critical_flows[0].model_copy(update={"name": "Different flow"})

    with pytest.raises(ValueError, match="must match the definitions"):
        service.save_report_workspace(
            audit.audit_id,
            workspace.model_copy(update={"critical_flows": (incorrect_flow,)}),
        )
