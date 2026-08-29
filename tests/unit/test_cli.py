from pathlib import Path

import pytest

from ai_qa_engineering.cli import main
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
