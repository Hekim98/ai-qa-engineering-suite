"""Structural, textual, and rendered-page verification for generated reports."""

from __future__ import annotations

import html as html_module
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from PIL import Image
from pypdf import PdfReader

from ai_qa_engineering.reporting.models import LaunchReport


class ReportVerificationError(ValueError):
    """Raised when a generated report is unsafe to present for visual review."""


@dataclass(frozen=True)
class VerificationResult:
    page_count: int
    page_images: tuple[Path, ...]
    checks: tuple[tuple[str, str], ...]


def _require_command(name: str) -> str:
    command = shutil.which(name)
    if command is None:
        raise ReportVerificationError(
            f"{name} is required to verify PDF output. Install Poppler and retry."
        )
    return command


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ReportVerificationError(f"Report verification command failed: {command[0]}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise ReportVerificationError(
            f"Report verification command failed: {Path(command[0]).name}: {detail}"
        )
    return result


def _numeric_page(path: Path) -> int:
    match = re.search(r"-(\d+)\.png$", path.name)
    return int(match.group(1)) if match else 0


def _normalized_text(value: str) -> str:
    return " ".join(value.split())


def verify_report_outputs(
    report: LaunchReport,
    html_path: Path,
    pdf_path: Path,
    *,
    render_directory: Path,
) -> VerificationResult:
    """Require valid HTML/PDF content and healthy PNG renders of every PDF page."""
    try:
        html = html_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ReportVerificationError("Generated HTML could not be read") from exc
    if not html.lstrip().lower().startswith("<!doctype html>"):
        raise ReportVerificationError("Generated HTML is missing its document declaration")
    unescaped_html = html_module.unescape(html)
    if (
        report.metadata.title not in unescaped_html
        or report.recommendation.value not in unescaped_html
    ):
        raise ReportVerificationError(
            "Generated HTML does not contain the verified report identity"
        )
    if "DRAFT · HUMAN VERIFICATION REQUIRED" in html:
        raise ReportVerificationError("Generated HTML still contains the draft warning")

    try:
        reader = PdfReader(pdf_path)
    except (OSError, ValueError) as exc:
        raise ReportVerificationError("Generated PDF could not be parsed") from exc
    if reader.is_encrypted:
        raise ReportVerificationError("Generated PDF must not be encrypted")
    page_count = len(reader.pages)
    if page_count < 1:
        raise ReportVerificationError("Generated PDF contains no pages")
    page_text = tuple((page.extract_text() or "").strip() for page in reader.pages)
    if any(not text for text in page_text):
        raise ReportVerificationError("Generated PDF contains a page with no extractable text")
    full_text = _normalized_text("\n".join(page_text))
    if (
        _normalized_text(report.metadata.title) not in full_text
        or _normalized_text(report.recommendation.value) not in full_text
    ):
        raise ReportVerificationError("Generated PDF does not contain the verified report identity")

    pdfinfo = _run([_require_command("pdfinfo"), str(pdf_path)])
    page_match = re.search(r"^Pages:\s+(\d+)$", pdfinfo.stdout, flags=re.MULTILINE)
    if page_match is None or int(page_match.group(1)) != page_count:
        raise ReportVerificationError("Poppler page count does not match the parsed PDF")

    render_directory.mkdir(parents=True, exist_ok=True)
    for old_page in render_directory.glob("page-*.png"):
        old_page.unlink()
    prefix = render_directory / "page"
    _run([_require_command("pdftoppm"), "-png", "-r", "120", str(pdf_path), str(prefix)])
    page_images = tuple(sorted(render_directory.glob("page-*.png"), key=_numeric_page))
    if len(page_images) != page_count:
        raise ReportVerificationError("Poppler did not render every PDF page")

    for image_path in page_images:
        try:
            with Image.open(image_path) as page_image:
                page_image.verify()
            with Image.open(image_path) as page_image:
                gray = page_image.convert("L")
                minimum, maximum = cast(tuple[int, int], gray.getextrema())
                width, height = page_image.size
        except (OSError, ValueError) as exc:
            raise ReportVerificationError(f"Rendered page is invalid: {image_path.name}") from exc
        if width < 500 or height < 700 or width >= height:
            raise ReportVerificationError(
                f"Rendered page has unexpected dimensions: {image_path.name}"
            )
        if maximum - minimum < 8:
            raise ReportVerificationError(f"Rendered page appears blank: {image_path.name}")

    return VerificationResult(
        page_count=page_count,
        page_images=page_images,
        checks=(
            (
                "HTML structure",
                "Self-contained document identity and final-state markers verified.",
            ),
            ("PDF structure", f"PDF parsed successfully with {page_count} page(s)."),
            ("PDF text", "Every page contains extractable text and the verified report identity."),
            ("Poppler inspection", "pdfinfo page count matches the parsed document."),
            ("Rendered pages", f"All {page_count} page(s) rendered to non-blank portrait PNGs."),
        ),
    )
