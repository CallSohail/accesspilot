"""Report serializers.

- ``to_json``: the canonical, machine-readable report.
- ``to_html``: a self-contained, human-readable HTML report (no external
  assets) so it can be downloaded and shared safely.

Both are generated from the already-validated ``Report`` model; we do no
extra analysis here.
"""

from __future__ import annotations

import json
from html import escape
from typing import Any

from .models import Finding, FindingSource, Report, Severity

_SEVERITY_ORDER = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}


def to_json(report: Report) -> str:
    return json.dumps(report.model_dump(mode="json"), indent=2, ensure_ascii=False)


def _sev_class(sev: Severity) -> str:
    return {"error": "sev-error", "warning": "sev-warning", "info": "sev-info"}[sev.value]


def _src_badge(src: FindingSource) -> str:
    labels = {
        FindingSource.DETERMINISTIC: "deterministic",
        FindingSource.AI: "AI suggestion",
        FindingSource.HUMAN: "needs human review",
    }
    return f'<span class="badge badge-{src.value}">{labels[src]}</span>'


def to_html(report: Report) -> str:
    findings = sorted(
        report.findings, key=lambda f: (_sev_class_rank(f.severity), f.location)
    )
    rows = []
    for f in findings:
        wcag = f'<code class="wcag">{escape(f.wcag_ref)}</code>' if f.wcag_ref else ""
        detail = (
            f'<p class="detail"><strong>Detail:</strong> {escape(f.detail)}</p>'
            if f.detail
            else ""
        )
        sug = (
            f'<div class="suggestion"><strong>Suggested:</strong> '
            f'<pre>{escape(f.suggestion)}</pre></div>'
            if f.suggestion
            else ""
        )
        rows.append(
            f"""
    <li class="finding {_sev_class(f.severity)}">
      <div class="finding-head">
        <span class="sev">{f.severity.value.upper()}</span>
        {_src_badge(f.source)}
        {wcag}
        <span class="loc">{escape(f.location)}</span>
      </div>
      <p class="desc">{escape(f.description)}</p>
      {detail}
      <p class="remediation"><strong>How to fix:</strong> {escape(f.remediation)}</p>
      {sug}
    </li>"""
        )

    suggestions = []
    for s in report.suggestions:
        suggestions.append(
            f"""
    <li class="sugg">
      <div class="sugg-loc">{escape(s.location)} <span class="badge badge-{s.source.value}">{s.source.value}</span></div>
      <div class="diff">
        <div class="diff-before"><div class="diff-label">Before</div><pre>{escape(s.before)}</pre></div>
        <div class="diff-after"><div class="diff-label">After</div><pre>{escape(s.after)}</pre></div>
      </div>
      <p class="sugg-why">{escape(s.rationale)}</p>
    </li>"""
        )

    notes = "".join(
        f"<li>{escape(n)}</li>" for n in report.notes
    ) or "<li>No notes.</li>"
    ai_line = (
        f"AI suggestions available (model: {escape(report.ai_model or 'n/a')})."
        if report.ai_available
        else "AI suggestions are not enabled for this run (no provider configured)."
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AccessPilot report — {escape(report.document.filename)}</title>
<style>
  :root {{ --err:#c0392b; --warn:#b9770e; --info:#2c6e9b; --bg:#0f172a; --card:#ffffff; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: system-ui, -apple-system, Segoe UI, sans-serif; margin:0; color:#1f2937; background:#f1f5f9; line-height:1.5; }}
  header {{ background:var(--bg); color:#fff; padding:24px 32px; }}
  header h1 {{ margin:0 0 4px; font-size:22px; }}
  header .sub {{ color:#cbd5e1; font-size:13px; }}
  .wrap {{ max-width:960px; margin:0 auto; padding:24px; }}
  .card {{ background:var(--card); border-radius:12px; padding:20px 24px; margin-bottom:20px; box-shadow:0 1px 3px rgba(0,0,0,.08); }}
  .stats {{ display:flex; gap:16px; flex-wrap:wrap; }}
  .stat {{ background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:12px 18px; min-width:90px; }}
  .stat .n {{ font-size:26px; font-weight:700; }}
  .stat .l {{ font-size:12px; color:#64748b; text-transform:uppercase; letter-spacing:.04em; }}
  .n-error {{ color:var(--err); }} .n-warning {{ color:var(--warn); }} .n-info {{ color:var(--info); }}
  h2 {{ font-size:16px; margin:0 0 12px; }}
  ul.findings {{ list-style:none; padding:0; margin:0; }}
  .finding {{ border-left:4px solid #cbd5e1; padding:12px 16px; margin-bottom:12px; background:#fff; border-radius:8px; }}
  .finding.sev-error {{ border-left-color:var(--err); }}
  .finding.sev-warning {{ border-left-color:var(--warn); }}
  .finding.sev-info {{ border-left-color:var(--info); }}
  .finding-head {{ display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin-bottom:6px; }}
  .sev {{ font-size:11px; font-weight:700; letter-spacing:.05em; padding:2px 8px; border-radius:999px; color:#fff; }}
  .sev-error + * {{ }}
  .loc {{ font-size:12px; color:#64748b; margin-left:auto; }}
  .desc {{ margin:0 0 6px; }}
  .detail {{ font-size:13px; color:#475569; }}
  .remediation {{ font-size:14px; }}
  .badge {{ font-size:11px; padding:2px 8px; border-radius:999px; background:#e2e8f0; color:#334155; }}
  .badge-ai {{ background:#ede9fe; color:#5b21b6; }}
  .badge-human {{ background:#fef3c7; color:#92400e; }}
  .badge-deterministic {{ background:#dcfce7; color:#166534; }}
  code.wcag {{ font-size:12px; background:#eff6ff; color:#1d4ed8; padding:2px 6px; border-radius:6px; }}
  .suggestion pre, .diff pre {{ background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:10px 12px; font-size:13px; white-space:pre-wrap; overflow:auto; }}
  ul.sugg {{ list-style:none; padding:0; margin:0; }}
  .sugg {{ border:1px solid #e2e8f0; border-radius:8px; padding:12px 16px; margin-bottom:12px; }}
  .diff {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; }}
  .diff-before pre {{ background:#fef2f2; border-color:#fecaca; }}
  .diff-after pre {{ background:#f0fdf4; border-color:#bbf7d0; }}
  .diff-label {{ font-size:11px; text-transform:uppercase; letter-spacing:.04em; color:#64748b; margin-bottom:4px; }}
  .sugg-why {{ font-size:13px; color:#475569; margin:8px 0 0; }}
  footer {{ text-align:center; color:#94a3b8; font-size:12px; padding:16px; }}
  @media (max-width:640px) {{ .diff {{ grid-template-columns:1fr; }} }}
</style>
</head>
<body>
<header>
  <h1>AccessPilot — Accessibility Report</h1>
  <div class="sub">{escape(report.document.filename)} · {report.document.kind.value} · {report.document.num_blocks} blocks · {escape(report.created_at.isoformat())}</div>
</header>
<div class="wrap">
  <div class="card">
    <h2>Summary</h2>
    <div class="stats">
      <div class="stat"><div class="n n-error">{report.summary.errors}</div><div class="l">Errors</div></div>
      <div class="stat"><div class="n n-warning">{report.summary.warnings}</div><div class="l">Warnings</div></div>
      <div class="stat"><div class="n n-info">{report.summary.info}</div><div class="l">Info</div></div>
      <div class="stat"><div class="n">{report.document.num_blocks}</div><div class="l">Blocks</div></div>
    </div>
    <p style="font-size:13px;color:#64748b;margin:14px 0 0;">{ai_line}</p>
  </div>

  <div class="card">
    <h2>Findings ({len(findings)})</h2>
    <ul class="findings">{''.join(rows) or '<li class="finding sev-info">No findings detected.</li>'}</ul>
  </div>

  <div class="card">
    <h2>Before / After suggestions ({len(report.suggestions)})</h2>
    <ul class="sugg">{''.join(suggestions) or '<li class="sugg">No before/after suggestions generated.</li>'}</ul>
  </div>

  <div class="card">
    <h2>Scope &amp; caveats</h2>
    <ul>{notes}</ul>
  </div>
</div>
<footer>Generated by AccessPilot · limited automated checks · not a conformance certification</footer>
</body>
</html>"""


def _sev_class_rank(sev: Severity) -> int:
    return _SEVERITY_ORDER[sev]
