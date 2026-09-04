from datetime import UTC, datetime
from pathlib import Path

import pytest

from ai_qa_engineering.artifacts import RunPaths
from ai_qa_engineering.config import load_config
from ai_qa_engineering.results import RunResult, RunStatus
from ai_qa_engineering.runner import build_pytest_command, execute_profiles


@pytest.mark.unit
def test_build_command_maps_profile_and_evidence_policies(tmp_path: Path) -> None:
    config = load_config("configs/example.yaml")
    paths = RunPaths.create(
        repository_root=tmp_path,
        artifact_root="artifacts/runs",
        project=config.project.name,
        profile="desktop-chromium",
        now=datetime(2026, 8, 28, tzinfo=UTC),
    )

    command = build_pytest_command(
        config_path=Path("configs/example.yaml"),
        config=config,
        profile_name="desktop-chromium",
        paths=paths,
    )

    assert command[0]
    assert command[command.index("--browser") + 1] == "chromium"
    assert command[command.index("--base-url") + 1] == "https://example.com/"
    assert command[command.index("-m", 4) + 1] == "full"
    assert command[command.index("--screenshot") + 1] == "only-on-failure"
    assert command[command.index("--video") + 1] == "retain-on-failure"
    assert command[command.index("--tracing") + 1] == "retain-on-failure"


@pytest.mark.unit
def test_build_command_isolates_detection_demo_marker(tmp_path: Path) -> None:
    config = load_config("configs/saucedemo.yaml")
    paths = RunPaths.create(
        repository_root=tmp_path,
        artifact_root="artifacts/runs",
        project=config.project.name,
        profile="detection-chromium",
        now=datetime(2026, 8, 28, tzinfo=UTC),
    )

    command = build_pytest_command(
        config_path=Path("configs/saucedemo.yaml"),
        config=config,
        profile_name="detection-chromium",
        paths=paths,
    )

    assert command[command.index("-m", 4) + 1] == "detection_demo"


@pytest.mark.unit
def test_execute_profiles_reads_structured_run_result(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(Path("configs/example.yaml").read_text(encoding="utf-8"))
    (tmp_path / "tests/example_project").mkdir(parents=True)

    def fake_run(command: list[str]) -> int:
        run_dir = Path(command[command.index("--ai-qa-run-dir") + 1])
        run_id = command[command.index("--ai-qa-run-id") + 1]
        result = RunResult(
            run_id=run_id,
            project="demo-ai-app",
            environment="staging",
            profile="desktop-chromium",
            browser="chromium",
            status=RunStatus.PASSED,
            started_at=datetime(2026, 8, 28, tzinfo=UTC),
            finished_at=datetime(2026, 8, 28, tzinfo=UTC),
            pytest_exit_code=0,
            tests=(),
        )
        (run_dir / "run.json").write_text(result.model_dump_json(), encoding="utf-8")
        return 0

    executions = execute_profiles(
        config_path,
        profile_names=["desktop-chromium"],
        repository_root=tmp_path,
        run_command=fake_run,
    )

    assert len(executions) == 1
    assert executions[0].status is RunStatus.PASSED
    assert executions[0].exit_code == 0
    assert (executions[0].run_dir / "logs/ai-qa.log").is_file()


@pytest.mark.unit
def test_execute_profiles_accepts_an_orchestrated_artifact_root(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(Path("configs/example.yaml").read_text(encoding="utf-8"))
    (tmp_path / "tests/example_project").mkdir(parents=True)

    def fake_run(command: list[str]) -> int:
        run_dir = Path(command[command.index("--ai-qa-run-dir") + 1])
        run_id = command[command.index("--ai-qa-run-id") + 1]
        result = RunResult(
            run_id=run_id,
            project="demo-ai-app",
            environment="staging",
            profile="desktop-chromium",
            browser="chromium",
            status=RunStatus.PASSED,
            started_at=datetime(2026, 9, 3, tzinfo=UTC),
            finished_at=datetime(2026, 9, 3, tzinfo=UTC),
            pytest_exit_code=0,
            tests=(),
        )
        (run_dir / "run.json").write_text(result.model_dump_json(), encoding="utf-8")
        return 0

    execution = execute_profiles(
        config_path,
        profile_names=["desktop-chromium"],
        repository_root=tmp_path,
        artifact_root="artifacts/audits/audit-1/profiles",
        run_command=fake_run,
    )[0]

    assert execution.run_dir.is_relative_to(tmp_path / "artifacts/audits/audit-1/profiles")
