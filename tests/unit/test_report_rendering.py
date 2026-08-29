import base64
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml
from pypdf import PdfReader

from ai_qa_engineering.reporting.html_report import render_html
from ai_qa_engineering.reporting.loader import ReportInputError, load_report_inputs
from ai_qa_engineering.reporting.models import LaunchReport
from ai_qa_engineering.reporting.pdf_report import render_pdf
from ai_qa_engineering.results import RunResult, RunStatus

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def _write_inputs(root: Path, *, evidence_exists: bool = True) -> tuple[Path, Path]:
    run_dir = root / "artifacts/runs/run-1"
    run_dir.mkdir(parents=True)
    run = RunResult(
        run_id="run-1",
        project="demo",
        environment="test",
        profile="desktop-chromium",
        browser="chromium",
        status=RunStatus.FAILED,
        started_at=datetime(2026, 8, 29, tzinfo=UTC),
        finished_at=datetime(2026, 8, 29, tzinfo=UTC),
        pytest_exit_code=1,
        tests=(),
    )
    (run_dir / "run.json").write_text(run.model_dump_json(), encoding="utf-8")
    evidence = root / "evidence.png"
    if evidence_exists:
        evidence.write_bytes(PNG)
    document = {
        "report": {
            "title": "Demo Launch Readiness Report",
            "project": "demo",
            "target": "https://example.com",
            "audit_date": "2026-08-29",
            "executive_summary": "The verified audit supports a conditional launch.",
            "assessments": [
                {"category": "core-flows", "status": "PASS", "rationale": "Flows pass"},
                {
                    "category": "reliability-error-handling",
                    "status": "PASS",
                    "rationale": "Reliable",
                },
                {"category": "ux-content", "status": "PASS", "rationale": "Clear"},
                {"category": "responsive", "status": "WARNING", "rationale": "Warning"},
                {"category": "accessibility-smoke", "status": "FAIL", "rationale": "Finding"},
                {"category": "network-health", "status": "FAIL", "rationale": "Finding"},
            ],
            "critical_flows": [
                {"id": "FLOW-001", "name": "Purchase", "status": "PASS", "evidence": "Automated"}
            ],
            "browser_coverage": [
                {
                    "profile": "desktop",
                    "browser": "Chromium",
                    "device": "Desktop",
                    "suite": "full",
                    "result": "passed with findings",
                }
            ],
            "limitations": ["Demo scope"],
            "allowlisted_observations": ["Third-party telemetry noise"],
        },
        "findings": [
            {
                "id": "F-001",
                "title": "Keyboard issue",
                "severity": "Major",
                "category": "accessibility-smoke",
                "source": "automated",
                "environment": "test",
                "browser/device": "Chromium desktop",
                "steps": ["Open page", "Use keyboard"],
                "expected": "Control receives focus",
                "actual": "Control does not receive focus",
                "evidence": ["evidence.png", "trace.zip"],
                "recommendation": "Use semantic controls",
                "status": "verified",
            },
            {
                "id": "D-001",
                "title": "Seeded image defect",
                "severity": "Major",
                "category": "content-integrity",
                "source": "detection-demonstration",
                "environment": "test",
                "browser/device": "Chromium desktop",
                "steps": ["Open seeded persona"],
                "expected": "Unique images",
                "actual": "Duplicate images",
                "evidence": ["evidence.png"],
                "recommendation": "Keep for demonstration",
                "status": "verified",
            },
        ],
    }
    (root / "trace.zip").write_bytes(b"trace")
    findings = root / "findings.yaml"
    findings.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    return run_dir, findings


@pytest.mark.unit
def test_renderers_use_same_validated_report(tmp_path: Path) -> None:
    run_dir, findings = _write_inputs(tmp_path)
    report: LaunchReport = load_report_inputs(run_dir, findings, repository_root=tmp_path)
    html_path = tmp_path / "report.html"
    pdf_path = tmp_path / "report.pdf"

    render_html(report, html_path, repository_root=tmp_path)
    render_pdf(report, pdf_path, repository_root=tmp_path)

    html = html_path.read_text(encoding="utf-8")
    pdf_text = "\n".join(page.extract_text() or "" for page in PdfReader(pdf_path).pages)
    assert report.score == 80
    assert "LAUNCH WITH CONDITIONS" in html
    assert "data:image/png;base64" in html
    assert "Detection Demonstration" in html
    assert "Demo Launch Readiness Report" in pdf_text
    assert "LAUNCH WITH CONDITIONS" in pdf_text
    assert "Keyboard issue" in pdf_text
    assert pdf_path.stat().st_size > 1_000


@pytest.mark.unit
def test_loader_rejects_missing_evidence(tmp_path: Path) -> None:
    run_dir, findings = _write_inputs(tmp_path, evidence_exists=False)

    with pytest.raises(ReportInputError, match="Evidence files not found"):
        load_report_inputs(run_dir, findings, repository_root=tmp_path)


@pytest.mark.unit
def test_loader_rejects_invalid_and_missing_inputs(tmp_path: Path) -> None:
    with pytest.raises(ReportInputError, match="Run result not found"):
        load_report_inputs(
            tmp_path / "missing", tmp_path / "missing.yaml", repository_root=tmp_path
        )

    run_dir, findings = _write_inputs(tmp_path)
    findings.write_text(json.dumps({"invalid": True}), encoding="utf-8")
    with pytest.raises(ReportInputError, match="Invalid report input"):
        load_report_inputs(run_dir, findings, repository_root=tmp_path)
