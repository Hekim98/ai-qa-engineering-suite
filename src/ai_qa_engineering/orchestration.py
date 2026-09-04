"""Run a complete multi-profile audit and prepare unverified review outputs."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml

from ai_qa_engineering.artifacts import safe_slug
from ai_qa_engineering.audit_models import (
    AttemptSummary,
    AuditedCriticalFlow,
    AuditResult,
    AuditStatus,
    CandidateFinding,
    CandidateStatus,
    ProfileAuditSummary,
    SecretPreflight,
)
from ai_qa_engineering.audit_reporting import render_draft_html, render_draft_pdf
from ai_qa_engineering.config import QAConfig, load_config
from ai_qa_engineering.paths import resolve_within
from ai_qa_engineering.results import RunResult, RunStatus, TestOutcome
from ai_qa_engineering.runner import ProfileExecution, execute_profiles
from ai_qa_engineering.secrets import configured_secret_names, resolve_accounts

ProfileExecutor = Callable[..., tuple[ProfileExecution, ...]]
FAILURE_OUTCOMES = {TestOutcome.FAILED, TestOutcome.ERROR}


@dataclass(frozen=True)
class AuditPaths:
    audit_id: str
    root: Path
    profiles: Path
    reports: Path

    @classmethod
    def create(
        cls,
        *,
        repository_root: Path,
        audit_root: Path,
        project: str,
        now: datetime,
    ) -> AuditPaths:
        timestamp = now.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
        base_id = f"{timestamp}-{safe_slug(project)}-audit"
        configured_root = resolve_within(repository_root, audit_root)
        audit_id = base_id
        root = resolve_within(configured_root, audit_id)
        counter = 2
        while root.exists():
            audit_id = f"{base_id}-{counter}"
            root = resolve_within(configured_root, audit_id)
            counter += 1
        profiles = root / "profiles"
        reports = root / "reports"
        profiles.mkdir(parents=True)
        reports.mkdir()
        return cls(audit_id=audit_id, root=root, profiles=profiles, reports=reports)


@dataclass(frozen=True)
class AuditOutputs:
    audit: AuditResult
    audit_directory: Path
    audit_json: Path
    candidate_findings: Path
    evidence_index: Path
    html_report: Path
    pdf_report: Path


def _load_result(execution: ProfileExecution) -> RunResult | None:
    path = execution.run_dir / "run.json"
    if not path.is_file():
        return None
    return RunResult.model_validate_json(path.read_text(encoding="utf-8"))


def _relative(path: Path, repository_root: Path) -> Path:
    return path.resolve().relative_to(repository_root)


def _attempt_summary(
    execution: ProfileExecution,
    result: RunResult | None,
    *,
    attempt: int,
    repository_root: Path,
) -> AttemptSummary:
    tests = result.tests if result else ()
    counts = {outcome: 0 for outcome in TestOutcome}
    for test in tests:
        counts[test.outcome] += 1
    failed_without_results = bool(result and result.status is RunStatus.FAILED and not tests)
    incomplete_reason = (
        result.incomplete_reason if result else "The profile did not produce run.json"
    )
    if failed_without_results:
        incomplete_reason = "The profile failed before producing any test result"
    return AttemptSummary(
        attempt=attempt,
        run_id=result.run_id if result else execution.run_dir.name,
        run_directory=_relative(execution.run_dir, repository_root),
        status=(
            RunStatus.INCOMPLETE if result is None or failed_without_results else result.status
        ),
        test_count=len(tests),
        passed=counts[TestOutcome.PASSED],
        failed=counts[TestOutcome.FAILED],
        skipped=counts[TestOutcome.SKIPPED],
        errors=counts[TestOutcome.ERROR],
        incomplete_reason=incomplete_reason,
    )


def _failed_tests(result: RunResult | None) -> set[str]:
    if result is None:
        return set()
    return {test.nodeid for test in result.tests if test.outcome in FAILURE_OUTCOMES}


def _test_title(nodeid: str) -> str:
    function_name = nodeid.rsplit("::", maxsplit=1)[-1].split("[", maxsplit=1)[0]
    return function_name.removeprefix("test_").replace("_", " ").strip().capitalize()


def _attempt_evidence(
    execution: ProfileExecution,
    result: RunResult | None,
    *,
    repository_root: Path,
) -> tuple[Path, ...]:
    run_json = execution.run_dir / "run.json"
    evidence = [_relative(run_json, repository_root)] if run_json.is_file() else []
    if result:
        evidence.extend(
            _relative(execution.run_dir / artifact, repository_root)
            for artifact in result.artifacts
        )
    return tuple(dict.fromkeys(evidence))


def _secret_preflight(config: QAConfig, repository_root: Path) -> SecretPreflight:
    if config.credentials is None:
        return SecretPreflight(
            configured=False,
            screenshot_masking_configured=bool(config.security.sensitive_selectors),
        )
    accounts = resolve_accounts(config.credentials, env_file=repository_root / ".env")
    return SecretPreflight(
        configured=True,
        account_names=tuple(accounts),
        required_environment_variables=configured_secret_names(config.credentials),
        screenshot_masking_configured=bool(config.security.sensitive_selectors),
    )


def run_audit(
    config_path: str | Path,
    *,
    profile_names: Sequence[str] | None = None,
    repository_root: str | Path | None = None,
    retry_failures: bool | None = None,
    profile_executor: ProfileExecutor = execute_profiles,
    now: datetime | None = None,
) -> AuditOutputs:
    """Run selected profiles, retry failures once, and write one review package."""
    root = Path(repository_root or Path.cwd()).resolve()
    source_path = Path(config_path).resolve()
    config = load_config(source_path)
    selected = list(profile_names or config.browser.profiles)
    unknown = sorted(set(selected) - set(config.browser.profiles))
    if unknown:
        raise ValueError(f"Unknown browser profiles: {', '.join(unknown)}")
    secret_preflight = _secret_preflight(config, root)
    started_at = now or datetime.now(UTC)
    paths = AuditPaths.create(
        repository_root=root,
        audit_root=config.orchestration.audit_root,
        project=config.project.name,
        now=started_at,
    )
    artifact_root = paths.profiles.relative_to(root)
    initial_executions = profile_executor(
        source_path,
        profile_names=selected,
        repository_root=root,
        artifact_root=artifact_root,
    )
    retry_enabled = (
        config.orchestration.retry_failures > 0 if retry_failures is None else retry_failures
    )
    profile_summaries: list[ProfileAuditSummary] = []
    finding_groups: dict[
        tuple[str, CandidateStatus],
        list[tuple[str, str, tuple[Path, ...]]],
    ] = defaultdict(list)
    evidence_records: list[dict[str, object]] = []

    for initial_execution in initial_executions:
        initial_result = _load_result(initial_execution)
        initial_failures = _failed_tests(initial_result)
        retry_execution: ProfileExecution | None = None
        retry_result: RunResult | None = None
        if (
            retry_enabled
            and initial_failures
            and initial_execution.status is not RunStatus.INCOMPLETE
        ):
            retry_execution = profile_executor(
                source_path,
                profile_names=[initial_execution.profile],
                repository_root=root,
                artifact_root=artifact_root,
            )[0]
            retry_result = _load_result(retry_execution)

        retry_failures_set = _failed_tests(retry_result)
        if retry_execution is None:
            persistent = initial_failures
            flaky: set[str] = set()
        elif retry_result is None or retry_result.status is RunStatus.INCOMPLETE:
            persistent = initial_failures
            flaky = set()
        else:
            persistent = initial_failures & retry_failures_set
            flaky = initial_failures ^ retry_failures_set

        attempts = [
            _attempt_summary(
                initial_execution,
                initial_result,
                attempt=1,
                repository_root=root,
            )
        ]
        executions_with_results = [(initial_execution, initial_result)]
        if retry_execution is not None:
            attempts.append(
                _attempt_summary(
                    retry_execution,
                    retry_result,
                    attempt=2,
                    repository_root=root,
                )
            )
            executions_with_results.append((retry_execution, retry_result))

        incomplete = any(item.status is RunStatus.INCOMPLETE for item in attempts)
        profile_status = (
            RunStatus.INCOMPLETE
            if incomplete
            else RunStatus.FAILED
            if persistent
            else RunStatus.PASSED
        )
        browser = config.browser.profiles[initial_execution.profile].engine.value
        profile_summaries.append(
            ProfileAuditSummary(
                profile=initial_execution.profile,
                browser=browser,
                device="Mobile"
                if config.browser.profiles[initial_execution.profile].mobile
                else "Desktop",
                suite=config.browser.profiles[initial_execution.profile].suite.value,
                status=profile_status,
                attempts=tuple(attempts),
                persistent_failures=tuple(sorted(persistent)),
                flaky_tests=tuple(sorted(flaky)),
            )
        )
        all_evidence = tuple(
            dict.fromkeys(
                evidence
                for execution, result in executions_with_results
                for evidence in _attempt_evidence(execution, result, repository_root=root)
            )
        )
        for nodeid in persistent:
            finding_groups[(nodeid, CandidateStatus.CANDIDATE)].append(
                (initial_execution.profile, browser, all_evidence)
            )
        for nodeid in flaky:
            finding_groups[(nodeid, CandidateStatus.FLAKY)].append(
                (initial_execution.profile, browser, all_evidence)
            )
        for execution, result in executions_with_results:
            evidence_records.append(
                {
                    "profile": initial_execution.profile,
                    "run_id": execution.run_dir.name,
                    "files": [
                        str(item)
                        for item in _attempt_evidence(execution, result, repository_root=root)
                    ],
                }
            )

    candidates: list[CandidateFinding] = []
    for index, ((nodeid, candidate_status), records) in enumerate(
        sorted(finding_groups.items(), key=lambda item: (item[0][1].value, item[0][0])),
        start=1,
    ):
        profiles = tuple(dict.fromkeys(record[0] for record in records))
        browsers = tuple(dict.fromkeys(record[1] for record in records))
        evidence = tuple(dict.fromkeys(path for record in records for path in record[2]))
        candidates.append(
            CandidateFinding(
                id=f"AUTO-{index:03d}",
                title=_test_title(nodeid),
                status=candidate_status,
                test=nodeid,
                profiles=profiles,
                browsers=browsers,
                occurrences=len(records),
                evidence=evidence,
            )
        )

    final_attempts = [profile.attempts[-1] for profile in profile_summaries]
    incomplete_audit = any(profile.status is RunStatus.INCOMPLETE for profile in profile_summaries)
    audit_status = (
        AuditStatus.INCOMPLETE
        if incomplete_audit
        else AuditStatus.NEEDS_REVIEW
        if candidates
        else AuditStatus.PASSED
    )
    audit = AuditResult(
        audit_id=paths.audit_id,
        project=config.project.name,
        environment=config.project.environment,
        target=str(config.project.base_url),
        status=audit_status,
        started_at=started_at,
        finished_at=datetime.now(UTC),
        profiles=tuple(profile_summaries),
        critical_flows=tuple(
            AuditedCriticalFlow(
                id=flow.id,
                name=flow.name,
                description=flow.description,
            )
            for flow in config.critical_flows
        ),
        candidate_findings=tuple(candidates),
        total_tests=sum(attempt.test_count for attempt in final_attempts),
        passed_tests=sum(attempt.passed for attempt in final_attempts),
        persistent_failures=sum(len(profile.persistent_failures) for profile in profile_summaries),
        flaky_tests=sum(len(profile.flaky_tests) for profile in profile_summaries),
        secret_preflight=secret_preflight,
    )
    audit_json = paths.root / "audit.json"
    candidate_path = paths.root / "candidate-findings.yaml"
    evidence_index = paths.root / "evidence-index.json"
    html_report = paths.reports / "draft-audit-report.html"
    pdf_report = paths.reports / "draft-audit-report.pdf"
    audit_json.write_text(audit.model_dump_json(indent=2), encoding="utf-8")
    candidate_payload = {
        "audit_id": audit.audit_id,
        "verification_required": True,
        "findings": [item.model_dump(mode="json") for item in audit.candidate_findings],
    }
    candidate_path.write_text(yaml.safe_dump(candidate_payload, sort_keys=False), encoding="utf-8")
    evidence_index.write_text(json.dumps(evidence_records, indent=2), encoding="utf-8")
    render_draft_html(audit, html_report)
    render_draft_pdf(audit, pdf_report)
    return AuditOutputs(
        audit=audit,
        audit_directory=paths.root,
        audit_json=audit_json,
        candidate_findings=candidate_path,
        evidence_index=evidence_index,
        html_report=html_report,
        pdf_report=pdf_report,
    )
