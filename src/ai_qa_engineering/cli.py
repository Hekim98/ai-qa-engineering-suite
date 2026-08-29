"""Command-line interface for the AI QA Engineering Suite."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from ai_qa_engineering.config import ConfigError, QAConfig, load_config
from ai_qa_engineering.runner import execute_profiles


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
    return parser


def _validation_summary(config: QAConfig) -> str:
    payload = {
        "status": "valid",
        "project": config.project.name,
        "environment": config.project.environment,
        "browser_profiles": sorted(config.browser.profiles),
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
        payload = [
            {
                "profile": execution.profile,
                "status": execution.status,
                "run_dir": str(execution.run_dir),
            }
            for execution in executions
        ]
        print(json.dumps(payload, indent=2))
        return max((execution.exit_code for execution in executions), default=0)

    parser.error(f"Unsupported command: {args.command}")
    return 2


def cli() -> None:
    raise SystemExit(main())
