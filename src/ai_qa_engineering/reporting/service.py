"""Coordinate validated report loading and both renderers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_qa_engineering.artifacts import safe_slug
from ai_qa_engineering.reporting.html_report import render_html
from ai_qa_engineering.reporting.loader import load_report_inputs
from ai_qa_engineering.reporting.models import LaunchReport
from ai_qa_engineering.reporting.pdf_report import render_pdf


@dataclass(frozen=True)
class ReportOutputs:
    report: LaunchReport
    html_path: Path
    pdf_path: Path


def generate_report_outputs(
    run_directory: str | Path,
    findings_path: str | Path,
    *,
    repository_root: str | Path | None = None,
    html_path: str | Path | None = None,
    pdf_path: str | Path | None = None,
) -> ReportOutputs:
    root = Path(repository_root or Path.cwd()).resolve()
    report = load_report_inputs(run_directory, findings_path, repository_root=root)
    slug = safe_slug(report.metadata.project)
    html_destination = Path(
        html_path or root / "output/html" / f"{slug}-launch-readiness-report.html"
    )
    pdf_destination = Path(pdf_path or root / "output/pdf" / f"{slug}-launch-readiness-report.pdf")
    render_html(report, html_destination, repository_root=root)
    render_pdf(report, pdf_destination, repository_root=root)
    return ReportOutputs(report=report, html_path=html_destination, pdf_path=pdf_destination)


def render_report_outputs(
    report: LaunchReport,
    *,
    repository_root: str | Path,
    html_path: str | Path,
    pdf_path: str | Path,
) -> ReportOutputs:
    """Render an already validated launch report to explicit safe destinations."""
    root = Path(repository_root).resolve()
    html_destination = Path(html_path)
    pdf_destination = Path(pdf_path)
    render_html(report, html_destination, repository_root=root)
    render_pdf(report, pdf_destination, repository_root=root)
    return ReportOutputs(report=report, html_path=html_destination, pdf_path=pdf_destination)
