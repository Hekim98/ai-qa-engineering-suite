"""Pytest integration for configuration, artifacts, diagnostics, and run summaries."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Generator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pytest
from playwright.sync_api import BrowserContext, Page

from ai_qa_engineering.api_testing import APIClient
from ai_qa_engineering.auth import SessionStateStore
from ai_qa_engineering.config import BrowserProfile, QAConfig, load_config
from ai_qa_engineering.observability import BrowserObserver
from ai_qa_engineering.results import APICheckRecord, RunResult, RunStatus, TestOutcome, TestResult
from ai_qa_engineering.secrets import (
    MissingSecretError,
    ResolvedCredentials,
    available_secret_values,
    redact_text,
    resolve_accounts,
    resolve_api_auth,
    resolve_credentials,
)


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
    api_checks: list[APICheckRecord] = field(default_factory=list)
    incomplete_reason: str | None = None
    secret_values: tuple[str, ...] = field(default_factory=tuple, repr=False)


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
def qa_account(qa_config: QAConfig) -> Callable[[str], ResolvedCredentials]:
    """Return a named test account resolver without exposing values in configuration."""
    if qa_config.credentials is None:
        raise pytest.UsageError(
            "This test requests a named account, but the project configuration has none"
        )
    try:
        accounts = resolve_accounts(qa_config.credentials)
    except MissingSecretError as exc:
        raise pytest.UsageError(str(exc)) from exc

    def resolve(name: str) -> ResolvedCredentials:
        try:
            return accounts[name]
        except KeyError as exc:
            available = ", ".join(sorted(accounts))
            raise pytest.UsageError(
                f"Unknown credential account: {name}. Available accounts: {available}"
            ) from exc

    return resolve


def _sensitive_mask_script(selectors: tuple[str, ...]) -> str:
    encoded = json.dumps(selectors)
    return f"""
        (() => {{
          const selectors = {encoded};
          const mask = () => {{
            for (const selector of selectors) {{
              for (const element of document.querySelectorAll(selector)) {{
                element.style.setProperty('filter', 'blur(10px)', 'important');
              }}
            }}
          }};
          document.addEventListener('DOMContentLoaded', mask);
          new MutationObserver(mask).observe(document, {{subtree: true, childList: true}});
        }})();
    """


@pytest.fixture(scope="session")
def qa_run_dir(pytestconfig: pytest.Config) -> Path:
    """Expose the isolated run directory for explicit audit evidence."""
    return Path(_required_option(pytestconfig, "--ai-qa-run-dir"))


@pytest.fixture
def qa_context_factory(
    new_context: Callable[..., BrowserContext],
    qa_profile: BrowserProfile,
    qa_config: QAConfig,
) -> Callable[..., BrowserContext]:
    """Create profile-sized contexts, optionally restoring ephemeral storage state."""

    def create(**overrides: Any) -> BrowserContext:
        options: dict[str, Any] = {
            "viewport": {
                "width": qa_profile.viewport.width,
                "height": qa_profile.viewport.height,
            },
            "is_mobile": qa_profile.mobile,
            "has_touch": qa_profile.mobile,
        }
        options.update(overrides)
        context = new_context(**options)
        if qa_config.security.sensitive_selectors:
            context.add_init_script(
                script=_sensitive_mask_script(qa_config.security.sensitive_selectors)
            )
        return context

    return create


@pytest.fixture
def qa_page(
    qa_context_factory: Callable[..., BrowserContext],
) -> Generator[Page, None, None]:
    """Create a page through the reusable profile-aware context factory."""
    yield qa_context_factory().new_page()


@pytest.fixture(scope="session")
def qa_session_store() -> Generator[SessionStateStore, None, None]:
    """Provide auto-deleted storage state that never enters the audit directory."""
    with TemporaryDirectory(prefix="ai-qa-session-") as directory:
        yield SessionStateStore(directory)


def _safe_test_name(nodeid: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", nodeid).strip("-")


@pytest.fixture
def api_client(
    qa_config: QAConfig,
    qa_run_dir: Path,
    request: pytest.FixtureRequest,
) -> Generator[APIClient, None, None]:
    """Provide a same-origin API checker that records redacted evidence per test."""
    if qa_config.api is None:
        raise pytest.UsageError("This test requests api_client, but the configuration has no api")
    reference = Path("api") / f"{_safe_test_name(request.node.nodeid)}.json"
    auth = resolve_api_auth(qa_config.api.auth)
    client = APIClient(
        qa_config.api,
        test_id=request.node.nodeid,
        evidence_path=qa_run_dir / reference,
        evidence_reference=str(reference),
        auth=auth,
        secret_values=available_secret_values(
            qa_config.credentials,
            api_auth=qa_config.api.auth,
        ),
    )
    yield client
    if _ACTIVE_RECORDER is not None:
        _ACTIVE_RECORDER.api_checks.extend(client.records)


@pytest.fixture
def browser_observer(
    qa_page: Page,
    qa_config: QAConfig,
    request: pytest.FixtureRequest,
    pytestconfig: pytest.Config,
) -> Generator[BrowserObserver, None, None]:
    secret_values = available_secret_values(
        qa_config.credentials,
        api_auth=qa_config.api.auth if qa_config.api else None,
    )
    observer = BrowserObserver(
        qa_config.network.allowlist,
        capture_console_errors=qa_config.network.capture_console_errors,
        capture_failed_requests=qa_config.network.capture_failed_requests,
        redact=lambda value: redact_text(value, secret_values),
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
    qa_config = load_config(Path(config_path))
    _ACTIVE_RECORDER = RunRecorder(
        run_id=str(run_id),
        config=qa_config,
        profile_name=str(profile_name),
        run_dir=Path(run_dir),
        secret_values=available_secret_values(
            qa_config.credentials,
            api_auth=qa_config.api.auth if qa_config.api else None,
        ),
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
    if error:
        error = redact_text(error, _ACTIVE_RECORDER.secret_values)
    if error and ("TargetUnavailableError" in error or "APIUnavailableError" in error):
        _ACTIVE_RECORDER.incomplete_reason = error.splitlines()[-1]
    _ACTIVE_RECORDER.tests.append(
        TestResult(
            nodeid=report.nodeid,
            outcome=outcome,
            duration_seconds=round(report.duration, 6),
            error=error,
        )
    )


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_runtest_makereport(
    item: pytest.Item,
    call: pytest.CallInfo[Any],
) -> Generator[None, pytest.TestReport, pytest.TestReport]:
    """Redact configured secrets before Pytest's terminal reporter sees a failure."""
    report = yield
    if _ACTIVE_RECORDER is not None and report.failed and report.longrepr:
        report.longrepr = redact_text(str(report.longrepr), _ACTIVE_RECORDER.secret_values)
    return report


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
        api_checks=tuple(recorder.api_checks),
        artifacts=artifacts,
        incomplete_reason=recorder.incomplete_reason,
    )
    (recorder.run_dir / "run.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
    _ACTIVE_RECORDER = None
