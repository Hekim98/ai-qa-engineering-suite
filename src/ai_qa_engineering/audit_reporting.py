"""Render explicitly unverified orchestrator summaries for human review."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ai_qa_engineering.audit_models import AuditResult


def _draft_footer(canvas: Any, document: Any) -> None:
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#D8E1DD"))
    canvas.line(18 * mm, 13 * mm, A4[0] - 18 * mm, 13 * mm)
    canvas.setFillColor(colors.HexColor("#58706B"))
    canvas.setFont("Helvetica", 7)
    canvas.drawString(18 * mm, 8.5 * mm, "AI QA Engineering Suite - Unverified Draft")
    canvas.drawRightString(A4[0] - 18 * mm, 8.5 * mm, f"Page {document.page}")
    canvas.restoreState()


def render_draft_html(audit: AuditResult, destination: Path) -> None:
    rows = "".join(
        "<tr>"
        f"<td>{escape(profile.profile)}</td>"
        f"<td>{escape(profile.browser)}</td>"
        f"<td>{escape(profile.status.value)}</td>"
        f"<td>{len(profile.attempts)}</td>"
        f"<td>{len(profile.persistent_failures)}</td>"
        f"<td>{len(profile.flaky_tests)}</td>"
        "</tr>"
        for profile in audit.profiles
    )
    findings = (
        "".join(
            "<li>"
            f"<strong>{escape(item.id)} · {escape(item.title)}</strong> "
            f"<span>{escape(item.status.value)}</span><br>"
            f"Profiles: {escape(', '.join(item.profiles))} · Test: <code>{escape(item.test)}</code>"
            "</li>"
            for item in audit.candidate_findings
        )
        or "<li>No automated failure candidates were produced.</li>"
    )
    api_rows = "".join(
        "<tr>"
        f"<td>{escape(item.name)}</td><td>{escape(item.profile)}</td>"
        f"<td>{escape(item.method)}</td><td><code>{escape(item.path)}</code></td>"
        f"<td>{escape(item.outcome.value)}</td>"
        f"<td>{item.latency_ms if item.latency_ms is not None else '—'} / "
        f"{item.latency_budget_ms} ms</td>"
        f"<td>{escape(item.response_schema or 'Not requested')}</td>"
        "</tr>"
        for item in audit.api_checks
    )
    api_section = ""
    if api_rows:
        api_section = (
            "<section><h2>API contract and workflow coverage</h2><table><thead><tr>"
            "<th>Check</th><th>Profile</th><th>Method</th><th>Path</th><th>Outcome</th>"
            "<th>Latency / budget</th><th>Schema</th></tr></thead>"
            f"<tbody>{api_rows}</tbody></table></section>"
        )
    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(audit.project)} Draft Audit</title>
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; color: #152520; background: #f4f7f6; }}
    main {{ max-width: 960px; margin: 0 auto; padding: 40px 24px 64px; }}
    header {{ background: #123f33; color: white; padding: 32px; border-radius: 16px; }}
    .draft {{ color: #ffcf70; font-weight: 800; letter-spacing: .08em; }}
    h1 {{ margin: 8px 0; }}
    section {{ background: white; margin-top: 18px; padding: 24px; border-radius: 14px; }}
    .metrics {{ display: flex; gap: 28px; flex-wrap: wrap; }}
    .metric strong {{ display: block; font-size: 28px; color: #126e52; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ padding: 10px; border-bottom: 1px solid #d8e1dd; text-align: left; }}
    th {{ background: #edf4f1; }}
    li {{ margin: 12px 0; line-height: 1.5; }}
    code {{ overflow-wrap: anywhere; }}
    .warning {{ border-left: 5px solid #d47a15; }}
  </style>
</head>
<body><main>
  <header>
    <div class="draft">DRAFT · HUMAN VERIFICATION REQUIRED</div>
    <h1>{escape(audit.project)} Automated Audit Summary</h1>
    <div>{escape(audit.audit_id)} · {escape(audit.environment)} · {escape(audit.target)}</div>
  </header>
  <section class="warning"><strong>No score or launch recommendation is published.</strong><br>
    {escape(audit.verification_note)}</section>
  <section>
    <h2>Execution summary</h2>
    <div class="metrics">
      <div class="metric"><strong>{audit.total_tests}</strong>tests</div>
      <div class="metric"><strong>{audit.passed_tests}</strong>passed</div>
      <div class="metric"><strong>{audit.persistent_failures}</strong>persistent failures</div>
      <div class="metric"><strong>{audit.flaky_tests}</strong>flaky tests</div>
      <div class="metric"><strong>{len(audit.api_checks)}</strong>API checks</div>
    </div>
  </section>
  <section><h2>Browser profiles</h2>
    <table><thead><tr><th>Profile</th><th>Browser</th><th>Status</th><th>Attempts</th><th>Persistent</th><th>Flaky</th></tr></thead>
    <tbody>{rows}</tbody></table>
  </section>
  <section><h2>Candidate findings</h2><ul>{findings}</ul></section>
  {api_section}
</main></body></html>"""
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(document, encoding="utf-8")


def render_draft_pdf(audit: AuditResult, destination: Path) -> None:
    styles = getSampleStyleSheet()
    document = SimpleDocTemplate(
        str(destination),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"{audit.project} Draft Audit",
    )
    story = [
        Paragraph("DRAFT - HUMAN VERIFICATION REQUIRED", styles["Heading2"]),
        Paragraph(f"{audit.project} Automated Audit Summary", styles["Title"]),
        Paragraph(f"Audit ID: {audit.audit_id}", styles["BodyText"]),
        Paragraph(f"Target: {audit.target}", styles["BodyText"]),
        Spacer(1, 8),
        Paragraph(
            "No score or launch recommendation is published. " + audit.verification_note,
            styles["BodyText"],
        ),
        Spacer(1, 12),
        Paragraph("Execution summary", styles["Heading2"]),
        Paragraph(
            f"Tests: {audit.total_tests} - Passed: {audit.passed_tests} - "
            f"Persistent failures: {audit.persistent_failures} - "
            f"Flaky tests: {audit.flaky_tests} - API checks: {len(audit.api_checks)}",
            styles["BodyText"],
        ),
        Spacer(1, 12),
        Paragraph("Browser profiles", styles["Heading2"]),
    ]
    profile_rows: list[list[str]] = [
        ["Profile", "Browser", "Status", "Attempts", "Persistent", "Flaky"]
    ]
    profile_rows.extend(
        [
            profile.profile,
            profile.browser,
            profile.status.value,
            str(len(profile.attempts)),
            str(len(profile.persistent_failures)),
            str(len(profile.flaky_tests)),
        ]
        for profile in audit.profiles
    )
    table = Table(
        profile_rows,
        colWidths=[43 * mm, 25 * mm, 29 * mm, 19 * mm, 26 * mm, 18 * mm],
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#136F52")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D8E1DD")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.extend([table, Spacer(1, 12), Paragraph("Candidate findings", styles["Heading2"])])
    if audit.candidate_findings:
        for item in audit.candidate_findings:
            story.append(
                Paragraph(
                    f"<b>{item.id} - {item.title}</b> [{item.status.value}]<br/>"
                    f"Profiles: {escape(', '.join(item.profiles))}<br/>"
                    f"Test: {escape(item.test)}",
                    styles["BodyText"],
                )
            )
            story.append(Spacer(1, 5))
    else:
        story.append(
            Paragraph("No automated failure candidates were produced.", styles["BodyText"])
        )
    if audit.api_checks:
        story.extend([Spacer(1, 12), Paragraph("API contract coverage", styles["Heading2"])])
        api_rows: list[list[str]] = [
            ["Check", "Profile", "Method", "Path", "Outcome", "Latency / budget"]
        ]
        api_rows.extend(
            [
                item.name,
                item.profile,
                item.method,
                item.path,
                item.outcome.value,
                (
                    f"{item.latency_ms:g} / {item.latency_budget_ms} ms"
                    if item.latency_ms is not None
                    else f"- / {item.latency_budget_ms} ms"
                ),
            ]
            for item in audit.api_checks
        )
        story.append(
            Table(
                api_rows,
                colWidths=[38 * mm, 28 * mm, 16 * mm, 38 * mm, 23 * mm, 27 * mm],
                repeatRows=1,
                style=TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#136F52")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D8E1DD")),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 6.5),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ]
                ),
            )
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    document.build(story, onFirstPage=_draft_footer, onLaterPages=_draft_footer)
