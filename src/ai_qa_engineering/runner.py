"""Execute configured pytest-playwright profiles in isolated subprocesses."""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from ai_qa_engineering.artifacts import RunPaths
from ai_qa_engineering.config import EvidencePolicy, QAConfig, load_config
from ai_qa_engineering.logging_config import configure_logging
from ai_qa_engineering.results import RunResult, RunStatus


@dataclass(frozen=True)
class ProfileExecution:
    profile: str
    run_dir: Path
    status: RunStatus
    exit_code: int


def _evidence_option(
    policy: EvidencePolicy,
    *,
    always: str,
    on_failure: str,
) -> str:
    return {
        EvidencePolicy.ALWAYS: always,
        EvidencePolicy.ON_FAILURE: on_failure,
        EvidencePolicy.OFF: "off",
    }[policy]


def build_pytest_command(
    *,
    config_path: Path,
    config: QAConfig,
    profile_name: str,
    paths: RunPaths,
) -> list[str]:
    profile = config.browser.profiles[profile_name]
    marker = profile.suite.value
    return [
        sys.executable,
        "-m",
        "pytest",
        str(config.project.tests_path),
        "-p",
        "ai_qa_engineering.pytest_plugin",
        "--no-cov",
        "-m",
        marker,
        "--browser",
        profile.engine,
        "--base-url",
        str(config.project.base_url),
        "--ai-qa-config",
        str(config_path),
        "--ai-qa-profile",
        profile_name,
        "--ai-qa-run-dir",
        str(paths.root),
        "--ai-qa-run-id",
        paths.run_id,
        "--output",
        str(paths.test_results),
        "--screenshot",
        _evidence_option(config.artifacts.screenshot, always="on", on_failure="only-on-failure"),
        "--video",
        _evidence_option(config.artifacts.video, always="on", on_failure="retain-on-failure"),
        "--tracing",
        _evidence_option(config.artifacts.trace, always="on", on_failure="retain-on-failure"),
    ]


def execute_profiles(
    config_path: str | Path,
    *,
    profile_names: Sequence[str] | None = None,
    repository_root: str | Path | None = None,
    run_command: Callable[[list[str]], int] | None = None,
) -> tuple[ProfileExecution, ...]:
    repo_root = Path(repository_root or Path.cwd()).resolve()
    source_path = Path(config_path).resolve()
    config = load_config(source_path)
    selected = list(profile_names or config.browser.profiles)
    unknown = sorted(set(selected) - set(config.browser.profiles))
    if unknown:
        raise ValueError(f"Unknown browser profiles: {', '.join(unknown)}")
    tests_path = repo_root / config.project.tests_path
    if not tests_path.is_dir():
        raise ValueError(f"Configured test directory not found: {tests_path}")

    command_runner = run_command or (
        lambda command: subprocess.run(command, check=False).returncode
    )
    executions: list[ProfileExecution] = []
    for profile_name in selected:
        paths = RunPaths.create(
            repository_root=repo_root,
            artifact_root=config.artifacts.root_dir,
            project=config.project.name,
            profile=profile_name,
        )
        logger = configure_logging(name=f"ai_qa.{paths.run_id}", log_dir=paths.logs)
        command = build_pytest_command(
            config_path=source_path,
            config=config,
            profile_name=profile_name,
            paths=paths,
        )
        logger.info("Starting browser profile %s", profile_name)
        exit_code = command_runner(command)
        result_path = paths.root / "run.json"
        if result_path.is_file():
            result = RunResult.model_validate(json.loads(result_path.read_text(encoding="utf-8")))
            status = result.status
        else:
            status = RunStatus.FAILED
        executions.append(
            ProfileExecution(
                profile=profile_name,
                run_dir=paths.root,
                status=status,
                exit_code=3 if status is RunStatus.INCOMPLETE else exit_code,
            )
        )
    return tuple(executions)
