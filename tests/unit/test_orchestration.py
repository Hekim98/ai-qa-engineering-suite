import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pypdf import PdfReader

from ai_qa_engineering.audit_models import AuditStatus, CandidateStatus
from ai_qa_engineering.orchestration import run_audit
from ai_qa_engineering.results import (
    RunResult,
    RunStatus,
)
from ai_qa_engineering.results import (
    TestOutcome as Outcome,
)
from ai_qa_engineering.results import (
    TestResult as Result,
)
from ai_qa_engineering.runner import ProfileExecution
from ai_qa_engineering.secrets import MissingSecretError


def _test(nodeid: str, outcome: Outcome) -> Result:
    return Result(nodeid=nodeid, outcome=outcome, duration_seconds=0.1)


def _executor(
    outcomes: dict[str, list[tuple[Result, ...]]],
) -> tuple[callable, dict[str, int]]:
    attempts: dict[str, int] = defaultdict(int)

    def execute(
        _config_path: Path,
        *,
        profile_names: list[str],
        repository_root: Path,
        artifact_root: Path,
    ) -> tuple[ProfileExecution, ...]:
        executions: list[ProfileExecution] = []
        for profile in profile_names:
            attempts[profile] += 1
            attempt = attempts[profile]
            tests = outcomes[profile][attempt - 1]
            status = (
                RunStatus.FAILED
                if any(test.outcome in {Outcome.FAILED, Outcome.ERROR} for test in tests)
                else RunStatus.PASSED
            )
            run_dir = repository_root / artifact_root / f"{profile}-attempt-{attempt}"
            run_dir.mkdir(parents=True)
            result = RunResult(
                run_id=run_dir.name,
                project="qa-practice-store",
                environment="public-training-demo",
                profile=profile,
                browser="chromium",
                status=status,
                started_at=datetime(2026, 9, 3, tzinfo=UTC),
                finished_at=datetime(2026, 9, 3, tzinfo=UTC),
                pytest_exit_code=1 if status is RunStatus.FAILED else 0,
                tests=tests,
            )
            (run_dir / "run.json").write_text(result.model_dump_json(), encoding="utf-8")
            executions.append(
                ProfileExecution(
                    profile=profile,
                    run_dir=run_dir,
                    status=status,
                    exit_code=result.pytest_exit_code,
                )
            )
        return tuple(executions)

    return execute, attempts


@pytest.mark.unit
def test_audit_combines_profiles_and_classifies_persistent_and_flaky_failures(
    tmp_path: Path,
) -> None:
    persistent = "tests/demo.py::test_checkout"
    unstable = "tests/demo.py::test_responsive_menu"
    execute, attempts = _executor(
        {
            "desktop-chromium": [
                (_test(persistent, Outcome.FAILED),),
                (_test(persistent, Outcome.FAILED),),
            ],
            "mobile-chromium": [
                (_test(unstable, Outcome.FAILED),),
                (_test(unstable, Outcome.PASSED),),
            ],
        }
    )

    outputs = run_audit(
        "configs/qapractice.yaml",
        profile_names=["desktop-chromium", "mobile-chromium"],
        repository_root=tmp_path,
        profile_executor=execute,
        now=datetime(2026, 9, 3, tzinfo=UTC),
    )

    assert outputs.audit.status is AuditStatus.NEEDS_REVIEW
    assert outputs.audit.persistent_failures == 1
    assert outputs.audit.flaky_tests == 1
    assert attempts == {"desktop-chromium": 2, "mobile-chromium": 2}
    assert {item.status for item in outputs.audit.candidate_findings} == {
        CandidateStatus.CANDIDATE,
        CandidateStatus.FLAKY,
    }
    assert outputs.audit.score is None
    assert outputs.audit.recommendation is None
    assert outputs.audit_json.is_file()
    assert outputs.candidate_findings.is_file()
    assert outputs.evidence_index.is_file()
    html = outputs.html_report.read_text(encoding="utf-8")
    pdf_text = "\n".join(page.extract_text() or "" for page in PdfReader(outputs.pdf_report).pages)
    assert "HUMAN VERIFICATION REQUIRED" in html
    assert "No score or launch recommendation" in pdf_text


@pytest.mark.unit
def test_audit_does_not_retry_a_clean_profile(tmp_path: Path) -> None:
    execute, attempts = _executor(
        {
            "desktop-chromium": [
                (_test("tests/demo.py::test_catalog", Outcome.PASSED),),
            ]
        }
    )

    outputs = run_audit(
        "configs/qapractice.yaml",
        profile_names=["desktop-chromium"],
        repository_root=tmp_path,
        profile_executor=execute,
        now=datetime(2026, 9, 3, tzinfo=UTC),
    )

    assert outputs.audit.status is AuditStatus.PASSED
    assert outputs.audit.total_tests == 1
    assert outputs.audit.passed_tests == 1
    assert outputs.audit.candidate_findings == ()
    assert attempts == {"desktop-chromium": 1}


@pytest.mark.unit
def test_audit_checks_declared_secrets_before_starting_profiles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("AI_QA_TEST_USER_EMAIL", raising=False)
    monkeypatch.delenv("AI_QA_TEST_USER_PASSWORD", raising=False)
    called = False

    def should_not_run(*_args: object, **_kwargs: object) -> tuple[ProfileExecution, ...]:
        nonlocal called
        called = True
        return ()

    with pytest.raises(MissingSecretError, match="AI_QA_TEST_USER_EMAIL"):
        run_audit(
            "configs/example.yaml",
            profile_names=["desktop-chromium"],
            repository_root=tmp_path,
            profile_executor=should_not_run,
        )

    assert called is False
    assert not (tmp_path / "artifacts/audits").exists()


@pytest.mark.unit
def test_evidence_index_contains_no_secret_values(tmp_path: Path) -> None:
    execute, _ = _executor(
        {"desktop-chromium": [(_test("tests/demo.py::test_ok", Outcome.PASSED),)]}
    )
    outputs = run_audit(
        "configs/qapractice.yaml",
        profile_names=["desktop-chromium"],
        repository_root=tmp_path,
        profile_executor=execute,
    )

    payload = json.loads(outputs.evidence_index.read_text(encoding="utf-8"))
    assert payload[0]["profile"] == "desktop-chromium"
    assert payload[0]["files"][0].endswith("run.json")
