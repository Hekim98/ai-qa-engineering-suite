from pathlib import Path
from types import SimpleNamespace

import pytest

from ai_qa_engineering.audit_models import AuditStatus
from ai_qa_engineering.cli import main
from ai_qa_engineering.reporting.loader import ReportInputError
from ai_qa_engineering.results import RunStatus
from ai_qa_engineering.runner import ProfileExecution


@pytest.mark.unit
def test_validate_command_returns_machine_readable_summary(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(["validate", "configs/example.yaml"])

    output = capsys.readouterr()
    assert exit_code == 0
    assert '"status": "valid"' in output.out
    assert '"desktop-chromium"' in output.out
    assert '"api_enabled": false' in output.out
    assert output.err == ""


@pytest.mark.unit
def test_validate_command_returns_two_for_missing_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(["validate", str(tmp_path / "missing.yaml")])

    output = capsys.readouterr()
    assert exit_code == 2
    assert "Configuration file not found" in output.err


@pytest.mark.unit
def test_test_command_prints_profile_summary(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    execution = ProfileExecution(
        profile="desktop-chromium",
        run_dir=tmp_path / "run",
        status=RunStatus.PASSED,
        exit_code=0,
    )
    monkeypatch.setattr(
        "ai_qa_engineering.cli.execute_profiles", lambda *_args, **_kwargs: (execution,)
    )

    exit_code = main(["test", "configs/example.yaml", "--profile", "desktop-chromium"])

    output = capsys.readouterr()
    assert exit_code == 0
    assert '"status": "passed"' in output.out


@pytest.mark.unit
def test_report_command_prints_verified_output_summary(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outputs = SimpleNamespace(
        report=SimpleNamespace(
            audit_status="complete",
            score=80,
            recommendation="LAUNCH WITH CONDITIONS",
        ),
        html_path=tmp_path / "report.html",
        pdf_path=tmp_path / "report.pdf",
    )
    monkeypatch.setattr("ai_qa_engineering.cli.generate_report_outputs", lambda *_args: outputs)

    exit_code = main(["report", str(tmp_path / "run"), "--findings", "findings.yaml"])

    output = capsys.readouterr()
    assert exit_code == 0
    assert '"score": 80' in output.out
    assert '"recommendation": "LAUNCH WITH CONDITIONS"' in output.out
    assert output.err == ""


@pytest.mark.unit
def test_report_command_returns_two_for_invalid_inputs(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*_args: object) -> None:
        raise ReportInputError("Evidence files not found: missing.png")

    monkeypatch.setattr("ai_qa_engineering.cli.generate_report_outputs", fail)

    exit_code = main(["report", str(tmp_path / "run"), "--findings", "findings.yaml"])

    output = capsys.readouterr()
    assert exit_code == 2
    assert "Evidence files not found" in output.err


@pytest.mark.unit
def test_audit_command_prints_combined_summary_and_review_exit_code(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audit = SimpleNamespace(
        audit_id="audit-1",
        status=AuditStatus.NEEDS_REVIEW,
        profiles=(object(), object()),
        total_tests=8,
        passed_tests=7,
        persistent_failures=1,
        flaky_tests=0,
        candidate_findings=(object(),),
        api_checks=(),
    )
    outputs = SimpleNamespace(
        audit=audit,
        audit_directory=tmp_path / "audit-1",
        html_report=tmp_path / "draft.html",
        pdf_report=tmp_path / "draft.pdf",
    )
    monkeypatch.setattr("ai_qa_engineering.cli.run_audit", lambda *_args, **_kwargs: outputs)

    exit_code = main(["audit", "configs/qapractice.yaml"])

    output = capsys.readouterr()
    assert exit_code == 1
    assert '"status": "needs-review"' in output.out
    assert '"candidate_findings": 1' in output.out
    assert '"api_checks": 0' in output.out
    assert '"score": null' in output.out


@pytest.mark.unit
def test_dashboard_command_starts_local_control_room(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: dict[str, object] = {}

    def fake_dashboard(**kwargs: object) -> None:
        called.update(kwargs)

    monkeypatch.setattr("ai_qa_engineering.cli.serve_dashboard", fake_dashboard)

    exit_code = main(["dashboard", "--port", "9123", "--no-open"])

    assert exit_code == 0
    assert called == {"port": 9123, "open_browser": False}
