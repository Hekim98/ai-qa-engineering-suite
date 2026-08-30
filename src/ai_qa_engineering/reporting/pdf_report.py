"""ReportLab renderer for portfolio-quality launch-readiness PDFs."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ai_qa_engineering.reporting.models import Finding, LaunchReport

INK = colors.HexColor("#102522")
GREEN = colors.HexColor("#136F52")
MINT = colors.HexColor("#42D49C")
PALE = colors.HexColor("#EDF4F1")
LINE = colors.HexColor("#D8E1DD")
MAJOR = colors.HexColor("#C85812")
MINOR = colors.HexColor("#9A6B00")
PURPLE = colors.HexColor("#6F55A5")


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ReportTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=28,
            leading=31,
            textColor=colors.white,
            alignment=TA_CENTER,
            spaceAfter=10,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle",
            parent=base["BodyText"],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#D9EEE7"),
            alignment=TA_CENTER,
        ),
        "h1": ParagraphStyle(
            "H1",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=23,
            textColor=GREEN,
            spaceBefore=8,
            spaceAfter=12,
        ),
        "h2": ParagraphStyle(
            "H2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=INK,
            spaceBefore=8,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontSize=9.2,
            leading=13,
            textColor=INK,
            spaceAfter=7,
        ),
        "small": ParagraphStyle(
            "Small",
            parent=base["BodyText"],
            fontSize=7.5,
            leading=10,
            textColor=INK,
        ),
        "badge": ParagraphStyle(
            "Badge",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=colors.white,
            alignment=TA_CENTER,
        ),
    }


def _footer(canvas: Any, document: Any) -> None:
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.line(18 * mm, 13 * mm, A4[0] - 18 * mm, 13 * mm)
    canvas.setFillColor(colors.HexColor("#58706B"))
    canvas.setFont("Helvetica", 7)
    canvas.drawString(18 * mm, 8.5 * mm, "AI QA Engineering Suite · Verified Launch Audit")
    canvas.drawRightString(A4[0] - 18 * mm, 8.5 * mm, f"Page {document.page}")
    canvas.restoreState()


def _table(data: list[list[Any]], widths: list[float], *, header: bool = True) -> Table:
    table = Table(data, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    commands: list[tuple[Any, ...]] = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.35, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]
    if header:
        commands.extend(
            [
                ("BACKGROUND", (0, 0), (-1, 0), GREEN),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
    for row in range(1 if header else 0, len(data)):
        if row % 2 == 0:
            commands.append(("BACKGROUND", (0, row), (-1, row), PALE))
    table.setStyle(TableStyle(commands))
    return table


def _image_flowables(path: Path) -> list[Image]:
    with PILImage.open(path) as source:
        width, height = source.size
        if height / width <= 3:
            max_width, max_height = 165 * mm, 95 * mm
            scale = min(max_width / width, max_height / height)
            return [Image(str(path), width=width * scale, height=height * scale)]

        crop_height = min(height, round(width * 2.3))
        previews: list[Image] = []
        for index in range(min(2, (height + crop_height - 1) // crop_height)):
            top = index * crop_height
            crop = source.crop((0, top, width, min(height, top + crop_height)))
            buffer = BytesIO()
            crop.save(buffer, format="PNG")
            buffer.seek(0)
            target_width = 60 * mm
            target_height = target_width * crop.height / crop.width
            previews.append(Image(buffer, width=target_width, height=target_height))
        return previews


def _finding_story(
    finding: Finding,
    *,
    repository_root: Path,
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    accent = MAJOR if finding.severity.value == "Major" else MINOR
    heading = Table(
        [
            [
                Paragraph(finding.severity.value, styles["badge"]),
                Paragraph(f"{finding.id} · {finding.title}", styles["h2"]),
            ]
        ],
        colWidths=[26 * mm, 145 * mm],
    )
    heading.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), accent),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("BOX", (0, 0), (-1, -1), 0.5, LINE),
            ]
        )
    )
    details = [
        [
            Paragraph("Environment", styles["small"]),
            Paragraph(finding.environment, styles["small"]),
        ],
        [
            Paragraph("Browser / device", styles["small"]),
            Paragraph(finding.browser_device, styles["small"]),
        ],
        [Paragraph("Expected", styles["small"]), Paragraph(finding.expected, styles["small"])],
        [Paragraph("Actual", styles["small"]), Paragraph(finding.actual, styles["small"])],
        [
            Paragraph("Recommendation", styles["small"]),
            Paragraph(finding.recommendation, styles["small"]),
        ],
    ]
    story: list[Any] = [heading, Spacer(1, 4), _table(details, [34 * mm, 137 * mm], header=False)]
    story.append(Paragraph("Reproduction", styles["h2"]))
    for index, step in enumerate(finding.steps, start=1):
        story.append(Paragraph(f"{index}. {step}", styles["body"]))
    image_flows: list[Image] = []
    other_evidence: list[Path] = []
    for relative in finding.evidence:
        path = repository_root / relative
        if path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
            image_flows.extend(_image_flowables(path))
        else:
            other_evidence.append(relative)
    if image_flows:
        if len(image_flows) == 1:
            story.extend([Spacer(1, 6), image_flows[0]])
        else:
            story.extend(
                [Spacer(1, 6), Table([image_flows], colWidths=[82 * mm] * len(image_flows))]
            )
    for evidence in other_evidence:
        story.append(Paragraph(f"Evidence: {evidence}", styles["small"]))
    story.extend([Spacer(1, 12)])
    return story


def render_pdf(report: LaunchReport, destination: Path, *, repository_root: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    styles = _styles()
    document = SimpleDocTemplate(
        str(destination),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=17 * mm,
        bottomMargin=18 * mm,
        title=report.metadata.title,
        author="AI QA Engineering Suite",
    )
    story: list[Any] = []
    cover = Table(
        [
            [Paragraph("AI QA ENGINEERING SUITE", styles["subtitle"])],
            [Paragraph(report.metadata.title, styles["title"])],
            [
                Paragraph(
                    (
                        f"{report.metadata.project} · {report.metadata.target}"
                        f"<br/>{report.metadata.audit_date}"
                    ),
                    styles["subtitle"],
                )
            ],
        ],
        colWidths=[174 * mm],
        rowHeights=[18 * mm, 45 * mm, 25 * mm],
    )
    cover.setStyle(
        TableStyle(
            [("BACKGROUND", (0, 0), (-1, -1), GREEN), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]
        )
    )
    story.extend([cover, Spacer(1, 14 * mm)])
    score_text = "Not published" if report.score is None else f"{report.score} / 100"
    summary = Table(
        [
            [
                Paragraph(
                    score_text, ParagraphStyle("Score", parent=styles["title"], textColor=GREEN)
                ),
                Paragraph(
                    report.recommendation.value,
                    ParagraphStyle("Rec", parent=styles["badge"], backColor=MAJOR, borderPadding=8),
                ),
            ]
        ],
        colWidths=[85 * mm, 85 * mm],
        rowHeights=[25 * mm],
    )
    summary.setStyle(
        TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("BOX", (0, 0), (-1, -1), 0.7, LINE)])
    )
    story.extend(
        [
            summary,
            Spacer(1, 8 * mm),
            Paragraph("Executive summary", styles["h1"]),
            Paragraph(report.metadata.executive_summary, styles["body"]),
            PageBreak(),
        ]
    )

    story.append(Paragraph("Launch readiness score", styles["h1"]))
    score_data: list[list[Any]] = [["Category", "Weight", "Status", "Earned", "Rationale"]]
    for category_score in report.category_scores:
        score_data.append(
            [
                Paragraph(category_score.category.value, styles["small"]),
                str(category_score.weight),
                category_score.status.value,
                f"{category_score.earned:g}",
                Paragraph(category_score.rationale, styles["small"]),
            ]
        )
    story.extend(
        [_table(score_data, [35 * mm, 15 * mm, 22 * mm, 16 * mm, 83 * mm]), Spacer(1, 9 * mm)]
    )
    story.append(Paragraph("Critical flows", styles["h1"]))
    flow_data: list[list[Any]] = [["ID", "Flow", "Status", "Evidence"]]
    for flow in report.metadata.critical_flows:
        flow_data.append(
            [
                Paragraph(flow.id, styles["small"]),
                Paragraph(flow.name, styles["small"]),
                Paragraph(flow.status.value, styles["small"]),
                Paragraph(flow.evidence, styles["small"]),
            ]
        )
    story.extend([_table(flow_data, [28 * mm, 49 * mm, 20 * mm, 74 * mm]), PageBreak()])

    story.append(Paragraph("Verified readiness findings", styles["h1"]))
    severity_order = {"Critical": 0, "Major": 1, "Minor": 2}
    for finding in sorted(
        report.readiness_findings, key=lambda item: severity_order[item.severity.value]
    ):
        story.extend(_finding_story(finding, repository_root=repository_root, styles=styles))

    story.extend([PageBreak(), Paragraph("Browser and device coverage", styles["h1"])])
    coverage: list[list[Any]] = [["Profile", "Browser", "Device", "Suite", "Result"]]
    for browser_coverage in report.metadata.browser_coverage:
        coverage.append(
            [
                Paragraph(browser_coverage.profile, styles["small"]),
                Paragraph(browser_coverage.browser, styles["small"]),
                Paragraph(browser_coverage.device, styles["small"]),
                Paragraph(browser_coverage.suite, styles["small"]),
                Paragraph(browser_coverage.result, styles["small"]),
            ]
        )
    story.extend(
        [_table(coverage, [38 * mm, 25 * mm, 39 * mm, 27 * mm, 42 * mm]), Spacer(1, 10 * mm)]
    )
    story.append(Paragraph("Network and console observations", styles["h1"]))
    for observation in report.metadata.allowlisted_observations:
        story.append(Paragraph(f"• {observation}", styles["body"]))
    story.append(Paragraph("Limitations", styles["h1"]))
    for limitation in report.metadata.limitations:
        story.append(Paragraph(f"• {limitation}", styles["body"]))

    if report.detection_findings:
        story.extend(
            [
                PageBreak(),
                Paragraph("Detection Demonstration", styles["h1"]),
                Paragraph(
                    "Seeded faulty personas prove the suite can detect material defects. "
                    "The following findings are excluded from the standard-user readiness score.",
                    styles["body"],
                ),
            ]
        )
        for finding in report.detection_findings:
            story.extend(_finding_story(finding, repository_root=repository_root, styles=styles))
    story.append(
        KeepTogether(
            [Spacer(1, 8 * mm), Paragraph(f"Verified source run: {report.run_id}", styles["small"])]
        )
    )
    document.build(story, onFirstPage=_footer, onLaterPages=_footer)
