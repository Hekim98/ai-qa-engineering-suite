import subprocess
from pathlib import Path

import pytest
from PIL import Image, ImageDraw
from pypdf import PdfReader

from ai_qa_engineering.reporting.html_report import render_html
from ai_qa_engineering.reporting.loader import load_report_inputs
from ai_qa_engineering.reporting.pdf_report import render_pdf
from ai_qa_engineering.reporting.verification import (
    ReportVerificationError,
    _normalized_text,
    verify_report_outputs,
)
from tests.unit.test_report_rendering import _write_inputs


def _render_fixture(root: Path) -> tuple[object, Path, Path]:
    run_directory, findings_path = _write_inputs(root)
    report = load_report_inputs(run_directory, findings_path, repository_root=root)
    html_path = root / "report.html"
    pdf_path = root / "report.pdf"
    render_html(report, html_path, repository_root=root)
    render_pdf(report, pdf_path, repository_root=root)
    return report, html_path, pdf_path


@pytest.mark.unit
def test_report_verification_checks_structure_text_and_every_rendered_page(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report, html_path, pdf_path = _render_fixture(tmp_path)
    page_count = len(PdfReader(pdf_path).pages)

    def fake_command(name: str) -> str:
        return name

    def fake_run(command: list[str]) -> subprocess.CompletedProcess[str]:
        if command[0] == "pdfinfo":
            return subprocess.CompletedProcess(command, 0, stdout=f"Pages:          {page_count}\n")
        prefix = Path(command[-1])
        for page_number in range(1, page_count + 1):
            image = Image.new("RGB", (990, 1400), "white")
            ImageDraw.Draw(image).rectangle((100, 100, 890, 300), fill="#136f52")
            image.save(prefix.with_name(f"{prefix.name}-{page_number}.png"))
        return subprocess.CompletedProcess(command, 0, stdout="")

    monkeypatch.setattr("ai_qa_engineering.reporting.verification._require_command", fake_command)
    monkeypatch.setattr("ai_qa_engineering.reporting.verification._run", fake_run)

    result = verify_report_outputs(
        report,
        html_path,
        pdf_path,
        render_directory=tmp_path / "pages",
    )

    assert result.page_count == page_count
    assert len(result.page_images) == page_count
    assert {name for name, _ in result.checks} == {
        "HTML structure",
        "PDF structure",
        "PDF text",
        "Poppler inspection",
        "Rendered pages",
    }


@pytest.mark.unit
def test_report_verification_normalizes_pdf_line_breaks() -> None:
    assert _normalized_text("LAUNCH WITH\n  CONDITIONS") == "LAUNCH WITH CONDITIONS"


@pytest.mark.unit
def test_report_verification_rejects_draft_or_unidentified_html(tmp_path: Path) -> None:
    report, html_path, pdf_path = _render_fixture(tmp_path)
    html_path.write_text("<html>DRAFT · HUMAN VERIFICATION REQUIRED</html>", encoding="utf-8")

    with pytest.raises(ReportVerificationError, match="document declaration"):
        verify_report_outputs(
            report,
            html_path,
            pdf_path,
            render_directory=tmp_path / "pages",
        )


@pytest.mark.integration
def test_report_verification_uses_real_poppler_for_every_page(tmp_path: Path) -> None:
    report, html_path, pdf_path = _render_fixture(tmp_path)

    result = verify_report_outputs(
        report,
        html_path,
        pdf_path,
        render_directory=tmp_path / "rendered-pages",
    )

    assert result.page_count == len(PdfReader(pdf_path).pages)
    assert all(page.stat().st_size > 1_000 for page in result.page_images)
