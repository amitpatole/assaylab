"""Self-contained Warm Paper HTML report — the validation-intelligence dashboard.

No server, no network dependency (branded fonts load progressively but degrade
to system stacks). Every dynamic string is HTML-escaped: test messages are
untrusted input, so the report must never become an XSS vector.
"""

from __future__ import annotations

from html import escape

from ..models import Report
from ..rca.risk import Risk
from .frontier import FrontierPoint, frontier_svg

# assaylab's Warm Paper accent — a desaturated validation-green (its own hue in
# the house register; siblings use cyan/amber/violet).
_ACCENT = "#5f8f6f"
_ACCENT_INK = "#3c6b4c"

_CSS = """
:root{--bg:#f7f5f1;--surface:#fffdf9;--panel:#efece4;--ink:#1b1a17;
--ink-muted:#6b6862;--ink-faint:#918d84;--rule:#e3ded4;--accent:#5f8f6f;--accent-ink:#3c6b4c}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto,sans-serif;line-height:1.5;
-webkit-font-smoothing:antialiased}
.wrap{max-width:900px;margin:0 auto;padding:56px 28px 80px}
.eyebrow{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--accent-ink);
font-weight:600;margin:0 0 8px}
h1{font-family:"Source Serif 4",Georgia,"Times New Roman",serif;font-weight:600;font-size:34px;
margin:0 0 6px;letter-spacing:-.01em}
h1::after{content:"";display:block;width:40px;height:3px;background:var(--accent);margin-top:14px}
h2{font-family:"Source Serif 4",Georgia,serif;font-weight:600;font-size:20px;
margin:44px 0 14px;padding-bottom:8px;border-bottom:1px solid var(--rule)}
.sub{color:var(--ink-muted);margin:0 0 4px}
.badge{display:inline-block;padding:3px 12px;border-radius:2px;font-weight:600;font-size:13px;
letter-spacing:.02em;border:1px solid var(--rule)}
.badge.pass{color:#3c6b4c;background:#eef3ee}
.badge.warn{color:#90641a;background:#f6f0e4}
.badge.fail{color:#9a3b34;background:#f6ebe9}
table{width:100%;border-collapse:collapse;font-size:14px;margin-top:8px}
th{text-align:left;font-weight:600;color:var(--ink-muted);font-size:12px;letter-spacing:.04em;
text-transform:uppercase;padding:8px 10px;border-bottom:1px solid var(--rule)}
td{padding:9px 10px;border-bottom:1px solid var(--rule);vertical-align:top}
tr:last-child td{border-bottom:none}
code,.mono{font-family:"JetBrains Mono",ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.5px}
.cause{color:var(--accent-ink);font-weight:600}
.msg{color:var(--ink-muted)}
.card{background:var(--surface);border:1px solid var(--rule);border-radius:3px;padding:20px 22px}
.frontier{background:var(--surface);border:1px solid var(--rule);border-radius:3px;padding:16px}
.foot{margin-top:64px;padding-top:16px;border-top:1px solid var(--rule);color:var(--ink-faint);
font-size:13px}
.mark{font-style:italic;color:var(--accent-ink)}
.num{font-variant-numeric:tabular-nums}
"""


def _verdict_class(v: str) -> str:
    return {"pass": "pass", "warn": "warn", "fail": "fail"}.get(v, "warn")


def _rca_rows(report: Report) -> str:
    if not report.issues:
        return '<tr><td colspan="6" class="msg">no failure signatures — all clear.</td></tr>'
    rows = []
    for i in report.issues:
        d = i.detail
        flaky = "yes" if d.get("flaky") else "no"
        rows.append(
            "<tr>"
            f'<td class="mono">{escape(str(i.kind))}</td>'
            f'<td class="cause">{escape(str(d.get("root_cause", "—")))}</td>'
            f'<td class="num">{escape(str(d.get("root_cause_confidence", "—")))}</td>'
            f'<td>{flaky}<span class="msg"> (p={escape(str(d.get("flaky_probability", "—")))})</span></td>'
            f'<td class="num">{escape(str(d.get("risk", "—")))}</td>'
            f'<td class="msg">{escape(i.message[:160])}</td>'
            "</tr>"
        )
    return "".join(rows)


def _risk_rows(ranked: list[Risk], top: int = 15) -> str:
    if not ranked:
        return '<tr><td colspan="5" class="msg">no test history.</td></tr>'
    rows = []
    for r in ranked[:top]:
        rows.append(
            "<tr>"
            f'<td class="num">{r.score:.3f}</td>'
            f'<td class="num">{r.forecast:.3f}</td>'
            f'<td class="num">{r.fail_rate*100:.1f}%</td>'
            f'<td class="num">{r.flip_rate*100:.1f}%</td>'
            f'<td class="mono">{escape(r.test_id)}</td>'
            "</tr>"
        )
    return "".join(rows)


def _frontier_rows(points: list[FrontierPoint]) -> str:
    rows = []
    for p in points:
        rows.append(
            "<tr>"
            f'<td class="num">{p.confidence*100:.2f}%</td>'
            f'<td class="num">{p.speedup:.2f}x</td>'
            f'<td class="num">{p.n_selected}/{p.n_total}</td>'
            f'<td class="num">{p.epsilon:.4f}</td>'
            "</tr>"
        )
    return "".join(rows)


def render_report(
    report: Report,
    *,
    ranked: list[Risk] | None = None,
    frontier_points: list[FrontierPoint] | None = None,
    title: str = "assaylab report",
    source_label: str = "",
) -> str:
    """Render a full Warm Paper HTML report. Returns a complete, standalone document."""
    ranked = ranked or []
    frontier_points = frontier_points or []
    vclass = _verdict_class(report.verdict.value)

    svg = frontier_svg(frontier_points, accent=_ACCENT_INK) if frontier_points else ""
    frontier_section = ""
    if frontier_points:
        frontier_section = f"""
    <h2>Confidence / speedup frontier</h2>
    <p class="sub">How much test time you save (x) against confidence retained (y).
    Each point is a selection at a different target.</p>
    <div class="frontier">{svg}</div>
    <table>
      <tr><th>confidence</th><th>speedup</th><th>tests run</th><th>epsilon</th></tr>
      {_frontier_rows(frontier_points)}
    </table>"""

    risk_section = ""
    if ranked:
        risk_section = f"""
    <h2>Riskiest tests</h2>
    <table>
      <tr><th>risk</th><th>forecast</th><th>fail%</th><th>flip%</th><th>test</th></tr>
      {_risk_rows(ranked)}
    </table>"""

    src = f' · <span class="mono">{escape(source_label)}</span>' if source_label else ""

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&family=JetBrains+Mono&family=Source+Serif+4:wght@400;600&display=swap" rel="stylesheet">
<style>{_CSS}</style></head>
<body><div class="wrap">
  <p class="eyebrow">validation intelligence{src}</p>
  <h1>{escape(title)}</h1>
  <p class="sub">Graded on the agentsensory contract.</p>
  <div class="card" style="margin-top:20px">
    <span class="badge {vclass}">{escape(report.verdict.value.upper())}</span>
    <span class="sub" style="margin-left:12px">{escape(report.summary)}</span>
  </div>

  <h2>Failure signatures &amp; root cause</h2>
  <table>
    <tr><th>kind</th><th>cause</th><th>conf</th><th>flaky</th><th>risk</th><th>message</th></tr>
    {_rca_rows(report)}
  </table>
{risk_section}
{frontier_section}

  <div class="foot">
    Generated by <span class="mono">assaylab</span> — validation intelligence for CI.
    <span class="mark">— amitpatole</span>
  </div>
</div></body></html>"""
