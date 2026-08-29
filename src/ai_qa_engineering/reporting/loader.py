"""Load and verify report inputs before any renderer sees them."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from ai_qa_engineering.paths import UnsafePathError, resolve_within
from ai_qa_engineering.reporting.models import FindingsDocument, LaunchReport
from ai_qa_engineering.reporting.scoring import score_audit
from ai_qa_engineering.results import RunResult


class ReportInputError(ValueError):
    """Raised when verified report inputs are missing or invalid."""


def load_report_inputs(
    run_directory: str | Path,
    findings_path: str | Path,
    *,
    repository_root: str | Path,
) -> LaunchReport:
    run_path = Path(run_directory) / "run.json"
    source_path = Path(findings_path)
    if not run_path.is_file():
        raise ReportInputError(f"Run result not found: {run_path}")
    if not source_path.is_file():
        raise ReportInputError(f"Findings file not found: {source_path}")
    try:
        run = RunResult.model_validate(json.loads(run_path.read_text(encoding="utf-8")))
        raw: Any = yaml.safe_load(source_path.read_text(encoding="utf-8"))
        document = FindingsDocument.model_validate(raw)
    except (OSError, UnicodeError, json.JSONDecodeError, yaml.YAMLError, ValidationError) as exc:
        raise ReportInputError(f"Invalid report input: {exc}") from exc

    missing: list[str] = []
    for finding in document.findings:
        for evidence in finding.evidence:
            try:
                evidence_path = resolve_within(repository_root, evidence)
            except UnsafePathError as exc:
                raise ReportInputError(f"Unsafe evidence path: {evidence}") from exc
            if not evidence_path.is_file():
                missing.append(str(evidence))
    if missing:
        raise ReportInputError(f"Evidence files not found: {', '.join(sorted(missing))}")
    return score_audit(document, run)
