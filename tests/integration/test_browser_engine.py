import time
from pathlib import Path

import pytest
from playwright.sync_api import Playwright

from ai_qa_engineering.audit_models import AuditStatus
from ai_qa_engineering.dashboard import DashboardService
from ai_qa_engineering.observability import BrowserObserver
from ai_qa_engineering.orchestration import run_audit
from ai_qa_engineering.results import RunStatus
from ai_qa_engineering.runner import execute_profiles
from ai_qa_engineering.testpacks import assert_basic_page_health


@pytest.mark.integration
def test_local_browser_captures_evidence_and_network_failure(
    playwright: Playwright,
    tmp_path: Path,
) -> None:
    browser = playwright.chromium.launch()
    video_dir = tmp_path / "video"
    context = browser.new_context(record_video_dir=video_dir)
    context.tracing.start(screenshots=True, snapshots=True, sources=True)
    page = context.new_page()
    observer = BrowserObserver()
    observer.attach(page)
    page.route("https://example.test/broken", lambda route: route.abort("failed"))
    page.set_content(
        """
        <html>
          <head><title>Local Browser Fixture</title></head>
          <body><main><h1>Fixture</h1></main></body>
        </html>
        """
    )
    assert_basic_page_health(page)
    page.evaluate("fetch('https://example.test/broken').catch(() => undefined)")
    page.screenshot(path=tmp_path / "page.png")
    context.tracing.stop(path=tmp_path / "trace.zip")
    context.close()
    browser.close()

    assert (tmp_path / "page.png").stat().st_size > 0
    assert (tmp_path / "trace.zip").stat().st_size > 0
    assert any(video_dir.glob("*.webm"))
    assert [record.url for record in observer.failed_requests] == ["https://example.test/broken"]


@pytest.mark.integration
def test_profile_runner_applies_configured_viewport() -> None:
    execution = execute_profiles(
        "configs/example.yaml",
        profile_names=["desktop-chromium"],
    )[0]

    assert execution.status is RunStatus.PASSED
    assert execution.exit_code == 0
    assert (execution.run_dir / "run.json").is_file()


@pytest.mark.integration
def test_orchestrator_builds_a_complete_local_audit_package(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests/client"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_local.py").write_text(
        """
import pytest


@pytest.mark.full
def test_local_page(qa_page):
    qa_page.set_content(
        '<main><h1>Local audit fixture</h1>'
        '<input id="secret" value="hidden"></main>'
    )
    assert qa_page.locator('h1').inner_text() == 'Local audit fixture'
    assert qa_page.locator('#secret').evaluate("element => element.style.filter") == 'blur(10px)'
""".strip(),
        encoding="utf-8",
    )
    config = tmp_path / "config.yaml"
    config.write_text(
        """
project:
  name: local-orchestrator-fixture
  base_url: https://example.test
  environment: local
  tests_path: tests/client
browser:
  profiles:
    desktop-chromium:
      engine: chromium
      suite: full
      viewport: {width: 1024, height: 768}
artifacts:
  root_dir: artifacts/runs
  screenshot: on-failure
  video: on-failure
  trace: on-failure
security:
  sensitive_selectors:
    - "#secret"
critical_flows:
  - id: LOCAL-001
    name: Local fixture renders
    description: The isolated browser fixture is visible.
""".strip(),
        encoding="utf-8",
    )

    outputs = run_audit(config, repository_root=tmp_path)

    assert outputs.audit.status is AuditStatus.PASSED
    assert outputs.audit.total_tests == 1
    assert outputs.audit.passed_tests == 1
    assert outputs.audit_json.is_file()
    assert outputs.html_report.is_file()
    assert outputs.pdf_report.is_file()


@pytest.mark.integration
def test_authenticated_sandbox_audit_restores_sessions_without_leaking_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository_root = Path.cwd()
    secrets = {
        "AUTH_SANDBOX_MEMBER_USERNAME": "member@example.test",
        "AUTH_SANDBOX_MEMBER_PASSWORD": "member-pass",
        "AUTH_SANDBOX_ADMIN_USERNAME": "admin@example.test",
        "AUTH_SANDBOX_ADMIN_PASSWORD": "admin-pass",
        "AUTH_SANDBOX_LOCKED_USERNAME": "locked@example.test",
        "AUTH_SANDBOX_LOCKED_PASSWORD": "locked-pass",
    }
    for name, value in secrets.items():
        monkeypatch.setenv(name, value)

    dashboard = DashboardService(repository_root)
    dashboard.start_audit("configs/auth-sandbox.yaml", ["desktop-chromium"])
    for _ in range(600):
        job = dashboard.list_jobs()[0]
        if job["status"] in {"completed", "failed"}:
            break
        time.sleep(0.05)

    assert job["status"] == "completed"
    audit_id = str(job["audit_id"])
    detail = dashboard.audit_detail(audit_id)
    audit = detail["audit"]
    assert isinstance(audit, dict)
    assert audit["status"] == AuditStatus.PASSED
    assert audit["total_tests"] == 5
    assert audit["secret_preflight"]["account_names"] == ["default", "admin", "locked"]
    assert detail["review"]["report_gate"] == "open"
    audit_directory = repository_root / "artifacts/audits" / audit_id
    persisted_text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in audit_directory.rglob("*")
        if path.is_file()
    )
    for secret in secrets.values():
        assert secret not in persisted_text
    assert not list(audit_directory.rglob("member.json"))
