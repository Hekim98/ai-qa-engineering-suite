"""Pytest integration for configuration, artifacts, diagnostics, and run summaries."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Generator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import BrowserContext, Page

from ai_qa_engineering.config import BrowserProfile, QAConfig, load_config
from ai_qa_engineering.observability import BrowserObserver
from ai_qa_engineering.results import RunResult, RunStatus, TestOutcome, TestResult
from ai_qa_engineering.secrets import ResolvedCredentials, resolve_credentials


@dataclass
class RunRecorder:
    run_id: str
    config: QAConfig
    profile_name: str
    run_dir: Path
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    tests: list[TestResult] = field(default_factory=list)
    console_errors: list[Any] = field(default_factory=list)
    failed_requests: list[Any] = field(default_factory=list)
    incomplete_reason: str | None = None


_ACTIVE_RECORDER: RunRecorder | None = None


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("ai-qa")
    group.addoption("--ai-qa-config", type=Path)
    group.addoption("--ai-qa-profile")
    group.addoption("--ai-qa-run-dir", type=Path)
    group.addoption("--ai-qa-run-id")


def _required_option(pytestconfig: pytest.Config, name: str) -> Any:
    value = pytestconfig.getoption(name)
    if value is None:
        raise pytest.UsageError(f"Required AI QA option is missing: {name}")
    return value


@pytest.fixture(scope="session")
def qa_config(pytestconfig: pytest.Config) -> QAConfig:
    return load_config(_required_option(pytestconfig, "--ai-qa-config"))


@pytest.fixture(scope="session")
def qa_profile(pytestconfig: pytest.Config, qa_config: QAConfig) -> BrowserProfile:
    profile_name = str(_required_option(pytestconfig, "--ai-qa-profile"))
    try:
        return qa_config.browser.profiles[profile_name]
    except KeyError as exc:
        raise pytest.UsageError(f"Unknown browser profile: {profile_name}") from exc


@pytest.fixture(scope="session")
def qa_credentials(qa_config: QAConfig) -> ResolvedCredentials:
    """Resolve the configured account without exposing secret values to tests or logs."""
    if qa_config.credentials is None:
        raise pytest.UsageError(
            "This test requests credentials, but the project configuration has none"
        )
    return resolve_credentials(qa_config.credentials)


@pytest.fixture(scope="session")
def qa_run_dir(pytestconfig: pytest.Config) -> Path:
    """Expose the isolated run directory for explicit audit evidence."""
    return Path(_required_option(pytestconfig, "--ai-qa-run-dir"))


@pytest.fixture
def qa_page(
    new_context: Callable[..., BrowserContext],
    qa_profile: BrowserProfile,
) -> Generator[Page, None, None]:
    """Create a profile-sized page through pytest-playwright's managed context factory."""
    context = new_context(
        viewport={
            "width": qa_profile.viewport.width,
            "height": qa_profile.viewport.height,
        },
        is_mobile=qa_profile.mobile,
        has_touch=qa_profile.mobile,
    )
    yield context.new_page()


def _safe_test_name(nodeid: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", nodeid).strip("-")


@pytest.fixture
def browser_observer(
    qa_page: Page,
    qa_config: QAConfig,
    request: pytest.FixtureRequest,
    pytestconfig: pytest.Config,
) -> Generator[BrowserObserver, None, None]:
    observer = BrowserObserver(
        qa_config.network.allowlist,
        capture_console_errors=qa_config.network.capture_console_errors,
        capture_failed_requests=qa_config.network.capture_failed_requests,
    )
    observer.attach(qa_page)
    yield observer

    run_dir = Path(_required_option(pytestconfig, "--ai-qa-run-dir"))
    output_path = run_dir / "observability" / f"{_safe_test_name(request.node.nodeid)}.json"
    payload = {
        "test": request.node.nodeid,
        "console_errors": [item.model_dump(mode="json") for item in observer.console_errors],
        "failed_requests": [item.model_dump(mode="json") for item in observer.failed_requests],
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if _ACTIVE_RECORDER is not None:
        _ACTIVE_RECORDER.console_errors.extend(observer.console_errors)
        _ACTIVE_RECORDER.failed_requests.extend(observer.failed_requests)


def pytest_sessionstart(session: pytest.Session) -> None:
    global _ACTIVE_RECORDER
    config_path = session.config.getoption("--ai-qa-config")
    run_dir = session.config.getoption("--ai-qa-run-dir")
    profile_name = session.config.getoption("--ai-qa-profile")
    run_id = session.config.getoption("--ai-qa-run-id")
    if not all((config_path, run_dir, profile_name, run_id)):
        _ACTIVE_RECORDER = None
        return
    _ACTIVE_RECORDER = RunRecorder(
        run_id=str(run_id),
        config=load_config(Path(config_path)),
        profile_name=str(profile_name),
        run_dir=Path(run_dir),
    )


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    if _ACTIVE_RECORDER is None:
        return
    if report.when == "setup" and report.failed:
        outcome = TestOutcome.ERROR
    elif report.when != "call":
        return
    else:
        outcome = TestOutcome(report.outcome)

    error = str(report.longrepr) if report.failed else None
    if error and "TargetUnavailableError" in error:
        _ACTIVE_RECORDER.incomplete_reason = error.splitlines()[-1]
    _ACTIVE_RECORDER.tests.append(
        TestResult(
            nodeid=report.nodeid,
            outcome=outcome,
            duration_seconds=round(report.duration, 6),
            error=error,
        )
    )


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    global _ACTIVE_RECORDER
    if _ACTIVE_RECORDER is None:
        return
    recorder = _ACTIVE_RECORDER
    profile = recorder.config.browser.profiles[recorder.profile_name]
    status = RunStatus.PASSED if exitstatus == 0 else RunStatus.FAILED
    if recorder.incomplete_reason:
        status = RunStatus.INCOMPLETE
    artifacts = tuple(
        str(path.relative_to(recorder.run_dir))
        for path in sorted(recorder.run_dir.rglob("*"))
        if path.is_file() and path.name != "run.json"
    )
    result = RunResult(
        run_id=recorder.run_id,
        project=recorder.config.project.name,
        environment=recorder.config.project.environment,
        profile=recorder.profile_name,
        browser=profile.engine,
        status=status,
        started_at=recorder.started_at,
        finished_at=datetime.now(UTC),
        pytest_exit_code=exitstatus,
        tests=tuple(recorder.tests),
        console_errors=tuple(recorder.console_errors),
        failed_requests=tuple(recorder.failed_requests),
        artifacts=artifacts,
        incomplete_reason=recorder.incomplete_reason,
    )
    (recorder.run_dir / "run.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
    _ACTIVE_RECORDER = None
