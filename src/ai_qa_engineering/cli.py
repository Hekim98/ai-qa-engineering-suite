"""Command-line interface for the AI QA Engineering Suite."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from ai_qa_engineering.config import ConfigError, QAConfig, load_config


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-qa", description="AI QA Engineering Suite")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser(
        "validate", description="Validate a project YAML configuration"
    )
    validate_parser.add_argument("config", type=Path)
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

    parser.error(f"Unsupported command: {args.command}")
    return 2


def cli() -> None:
    raise SystemExit(main())
