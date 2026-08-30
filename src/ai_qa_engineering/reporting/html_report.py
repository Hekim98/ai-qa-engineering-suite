"""Self-contained HTML renderer for launch-readiness reports."""

from __future__ import annotations

import base64
import html
import mimetypes
from pathlib import Path

from ai_qa_engineering.reporting.models import Finding, LaunchReport, Severity


def _escape(value: object) -> str:
    return html.escape(str(value))


def _image_data(path: Path) -> str | None:
    if path.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
        return None
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _finding_card(finding: Finding, repository_root: Path) -> str:
    evidence: list[str] = []
    for relative in finding.evidence:
        path = repository_root / relative
        image = _image_data(path)
        if image:
            evidence.append(
                f'<img class="evidence" src="{image}" alt="Evidence for {_escape(finding.id)}">'
            )
        else:
            evidence.append(f'<code class="path">{_escape(relative)}</code>')
    steps = "".join(f"<li>{_escape(step)}</li>" for step in finding.steps)
    return f"""
    <article class="finding {finding.severity.value.lower()}">
      <div class="finding-heading">
        <span class="severity">{_escape(finding.severity.value)}</span>
        <span class="finding-id">{_escape(finding.id)}</span>
      </div>
      <h3>{_escape(finding.title)}</h3>
      <p class="meta">{_escape(finding.category)} · {_escape(finding.browser_device)}</p>
      <div class="finding-grid">
        <div><h4>Reproduction</h4><ol>{steps}</ol></div>
        <div><h4>Expected</h4><p>{_escape(finding.expected)}</p></div>
        <div><h4>Actual</h4><p>{_escape(finding.actual)}</p></div>
        <div><h4>Recommendation</h4><p>{_escape(finding.recommendation)}</p></div>
      </div>
      <div class="evidence-grid">{"".join(evidence)}</div>
    </article>
    """


def render_html(report: LaunchReport, destination: Path, *, repository_root: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    score_value = "—" if report.score is None else str(report.score)
    score_degrees = 0 if report.score is None else report.score * 3.6
    score_rows = "".join(
        f"<tr><td>{_escape(item.category.value)}</td><td>{item.weight}</td>"
        f"<td><span class='status {item.status.value.lower()}'>{item.status.value}</span></td>"
        f"<td>{item.earned:g}</td><td>{_escape(item.rationale)}</td></tr>"
        for item in report.category_scores
    )
    flow_rows = "".join(
        f"<tr><td>{_escape(flow.id)}</td><td>{_escape(flow.name)}</td>"
        f"<td><span class='status {flow.status.value.lower()}'>{flow.status.value}</span></td>"
        f"<td>{_escape(flow.evidence)}</td></tr>"
        for flow in report.metadata.critical_flows
    )
    coverage_rows = "".join(
        f"<tr><td>{_escape(item.profile)}</td><td>{_escape(item.browser)}</td>"
        f"<td>{_escape(item.device)}</td><td>{_escape(item.suite)}</td>"
        f"<td>{_escape(item.result)}</td></tr>"
        for item in report.metadata.browser_coverage
    )
    limitations = "".join(f"<li>{_escape(item)}</li>" for item in report.metadata.limitations)
    observations = "".join(
        f"<li>{_escape(item)}</li>" for item in report.metadata.allowlisted_observations
    )
    readiness_cards = "".join(
        _finding_card(finding, repository_root)
        for severity in Severity
        for finding in report.readiness_findings
        if finding.severity is severity
    )
    detection_cards = "".join(
        _finding_card(finding, repository_root) for finding in report.detection_findings
    )
    detection_section = ""
    if detection_cards:
        detection_section = (
            '<section class="detection"><h2>Detection Demonstration — excluded from readiness</h2>'
            "<p>Seeded faulty personas prove that the suite detects material defects. "
            "These findings do not affect the standard-user score.</p>"
            f"{detection_cards}</section>"
        )
    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{_escape(report.metadata.title)}</title>
  <style>
    :root {{ --ink:#102522; --muted:#58706b; --paper:#f4f7f5; --panel:#fff;
      --green:#136f52; --mint:#42d49c; --critical:#a61b29; --major:#c85812;
      --minor:#9a6b00; --line:#d8e1dd; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; color:var(--ink); background:var(--paper); font:15px/1.55 Inter,Arial,sans-serif; }}
    header {{ background:linear-gradient(135deg,#0d3028,#136f52); color:white; padding:56px max(6vw,24px); }}
    header p {{ max-width:780px; color:#d9eee7; }}
    .eyebrow {{ text-transform:uppercase; letter-spacing:.14em; font-size:12px; font-weight:700; }}
    h1 {{ margin:.25em 0; font-size:clamp(34px,5vw,60px); line-height:1.05; }}
    h2 {{ margin-top:0; font-size:27px; }} h3 {{ margin:.4rem 0; }} h4 {{ margin:.2rem 0; }}
    main {{ max-width:1160px; margin:-28px auto 60px; padding:0 22px; }}
    section,.hero-card {{ background:var(--panel); border:1px solid var(--line); border-radius:16px; padding:28px; margin:22px 0; box-shadow:0 10px 30px #163d3020; }}
    .hero-card {{ display:grid; grid-template-columns:190px 1fr; gap:30px; align-items:center; }}
    .score {{ width:160px; height:160px; border-radius:50%; display:grid; place-items:center;
      background:conic-gradient(var(--mint) {score_degrees}deg,#dfe9e5 0); position:relative; }}
    .score:after {{ content:""; width:126px; height:126px; border-radius:50%; background:white; position:absolute; }}
    .score strong {{ z-index:1; font-size:42px; }} .score small {{ z-index:1; position:absolute; margin-top:57px; color:var(--muted); }}
    .recommendation {{ display:inline-block; color:white; background:var(--major); border-radius:999px; padding:9px 16px; font-weight:800; letter-spacing:.04em; }}
    table {{ width:100%; border-collapse:collapse; font-size:14px; }} th {{ text-align:left; background:#edf4f1; }}
    th,td {{ padding:11px 10px; border-bottom:1px solid var(--line); vertical-align:top; }}
    .status,.severity {{ display:inline-block; border-radius:999px; padding:3px 9px; font-size:11px; font-weight:800; }}
    .pass {{ background:#d9f4e9; color:#075b3e; }} .warning {{ background:#fff0c2; color:#725000; }}
    .fail,.blocked {{ background:#ffe0dd; color:#8f211d; }}
    .finding {{ border-left:5px solid var(--minor); padding:22px; margin:20px 0; background:#fbfcfb; border-radius:8px; }}
    .finding.major {{ border-left-color:var(--major); }} .finding.critical {{ border-left-color:var(--critical); }}
    .finding.major .severity {{ background:#ffe8d9; color:#8d3505; }} .finding.minor .severity {{ background:#fff1bd; color:#705000; }}
    .finding-heading {{ display:flex; gap:10px; align-items:center; }} .finding-id,.meta {{ color:var(--muted); }}
    .finding-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:18px; }}
    .evidence-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:12px; margin-top:18px; }}
    .evidence {{ width:100%; max-height:620px; object-fit:contain; object-position:top; border:1px solid var(--line); border-radius:8px; background:white; }}
    .path {{ display:block; overflow-wrap:anywhere; background:#edf2f0; padding:10px; border-radius:6px; }}
    .detection {{ border:2px dashed #6f55a5; background:#f8f4ff; }}
    footer {{ text-align:center; color:var(--muted); padding:30px; }}
    @media (max-width:720px) {{ .hero-card,.finding-grid {{ grid-template-columns:1fr; }} table {{ display:block; overflow-x:auto; }} }}
    @media print {{ body {{ background:white; }} section,.hero-card {{ box-shadow:none; break-inside:avoid; }} }}
  </style>
</head>
<body>
<header><div class="eyebrow">AI QA Engineering Suite · Verified Audit</div>
<h1>{_escape(report.metadata.title)}</h1>
<p>{_escape(report.metadata.project)} · {_escape(report.metadata.target)} · {_escape(report.metadata.audit_date)}</p></header>
<main>
  <div class="hero-card"><div class="score"><strong>{score_value}</strong><small>/ 100</small></div>
    <div><span class="recommendation">{_escape(report.recommendation.value)}</span><h2>Executive summary</h2>
    <p>{_escape(report.metadata.executive_summary)}</p></div></div>
  <section><h2>Launch readiness score</h2><table><thead><tr><th>Category</th><th>Weight</th><th>Status</th><th>Earned</th><th>Evidence-based rationale</th></tr></thead><tbody>{score_rows}</tbody></table></section>
  <section><h2>Critical flows</h2><table><thead><tr><th>ID</th><th>Flow</th><th>Status</th><th>Evidence</th></tr></thead><tbody>{flow_rows}</tbody></table></section>
  <section><h2>Verified readiness findings</h2>{readiness_cards or "<p>No readiness findings.</p>"}</section>
  <section><h2>Browser and device coverage</h2><table><thead><tr><th>Profile</th><th>Browser</th><th>Device</th><th>Suite</th><th>Result</th></tr></thead><tbody>{coverage_rows}</tbody></table></section>
  <section><h2>Network and console observations</h2><ul>{observations or "<li>No allowlisted observations.</li>"}</ul></section>
  <section><h2>Limitations</h2><ul>{limitations}</ul></section>
  {detection_section}
</main><footer>Generated from verified structured results · Run {_escape(report.run_id)}</footer>
</body></html>"""
    destination.write_text(document, encoding="utf-8")
