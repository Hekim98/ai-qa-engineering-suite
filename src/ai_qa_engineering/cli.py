"""Command-line interface for the AI QA Engineering Suite."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from ai_qa_engineering.audit_models import AuditStatus
from ai_qa_engineering.config import ConfigError, QAConfig, load_config
from ai_qa_engineering.dashboard import serve_dashboard
from ai_qa_engineering.orchestration import run_audit
from ai_qa_engineering.reporting import generate_report_outputs
from ai_qa_engineering.reporting.loader import ReportInputError
from ai_qa_engineering.runner import execute_profiles
from ai_qa_engineering.secrets import MissingSecretError


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-qa", description="AI QA Engineering Suite")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser(
        "validate", description="Validate a project YAML configuration"
    )
    validate_parser.add_argument("config", type=Path)

    test_parser = subparsers.add_parser(
        "test", description="Run one or more configured browser profiles"
    )
    test_parser.add_argument("config", type=Path)
    test_parser.add_argument("--profile", action="append", dest="profiles")

    audit_parser = subparsers.add_parser(
        "audit", description="Run, retry, combine, and summarize a complete browser audit"
    )
    audit_parser.add_argument("config", type=Path)
    audit_parser.add_argument("--profile", action="append", dest="profiles")
    audit_parser.add_argument(
        "--no-retry",
        action="store_false",
        dest="retry_failures",
        default=None,
        help="Do not repeat failed profiles for flaky-test classification",
    )

    report_parser = subparsers.add_parser(
        "report", description="Generate verified HTML and PDF launch-readiness reports"
    )
    report_parser.add_argument("run_directory", type=Path)
    report_parser.add_argument("--findings", type=Path, required=True)

    dashboard_parser = subparsers.add_parser(
        "dashboard", description="Open the local audit and human-review control room"
    )
    dashboard_parser.add_argument("--port", type=int, default=8765)
    dashboard_parser.add_argument(
        "--no-open",
        action="store_false",
        dest="open_browser",
        help="Start the local dashboard without opening a browser window",
    )
    return parser


def _validation_summary(config: QAConfig) -> str:
    payload = {
        "status": "valid",
        "project": config.project.name,
        "environment": config.project.environment,
        "browser_profiles": sorted(config.browser.profiles),
        "api_enabled": config.api is not None,
        "api_authentication": config.api.auth.kind if config.api else None,
        "critical_flows": [flow.id for flow in config.critical_flows],
    }
    return json.dumps(payload, indent=2)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "validate":
        try:
            config = load_config(args.config)
        except ConfigError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        print(_validation_summary(config))
        return 0

    if args.command == "test":
        try:
            executions = execute_profiles(args.config, profile_names=args.profiles)
        except (ConfigError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
        test_payload = [
            {
                "profile": execution.profile,
                "status": execution.status,
                "run_dir": str(execution.run_dir),
            }
            for execution in executions
        ]
        print(json.dumps(test_payload, indent=2))
        return max((execution.exit_code for execution in executions), default=0)

    if args.command == "audit":
        try:
            audit_outputs = run_audit(
                args.config,
                profile_names=args.profiles,
                retry_failures=args.retry_failures,
            )
        except (ConfigError, MissingSecretError, OSError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
        payload = {
            "audit_id": audit_outputs.audit.audit_id,
            "status": audit_outputs.audit.status,
            "profiles": len(audit_outputs.audit.profiles),
            "tests": audit_outputs.audit.total_tests,
            "passed": audit_outputs.audit.passed_tests,
            "persistent_failures": audit_outputs.audit.persistent_failures,
            "flaky_tests": audit_outputs.audit.flaky_tests,
            "candidate_findings": len(audit_outputs.audit.candidate_findings),
            "api_checks": len(audit_outputs.audit.api_checks),
            "score": None,
            "recommendation": None,
            "audit_directory": str(audit_outputs.audit_directory),
            "draft_html": str(audit_outputs.html_report),
            "draft_pdf": str(audit_outputs.pdf_report),
        }
        print(json.dumps(payload, indent=2))
        if audit_outputs.audit.status is AuditStatus.INCOMPLETE:
            return 3
        if audit_outputs.audit.status is AuditStatus.NEEDS_REVIEW:
            return 1
        return 0

    if args.command == "report":
        try:
            report_outputs = generate_report_outputs(args.run_directory, args.findings)
        except (ReportInputError, OSError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
        report_payload = {
            "status": report_outputs.report.audit_status,
            "score": report_outputs.report.score,
            "recommendation": report_outputs.report.recommendation,
            "html": str(report_outputs.html_path),
            "pdf": str(report_outputs.pdf_path),
        }
        print(json.dumps(report_payload, indent=2))
        return 0

    if args.command == "dashboard":
        try:
            serve_dashboard(port=args.port, open_browser=args.open_browser)
        except (OSError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2


def cli() -> None:
    raise SystemExit(main())
