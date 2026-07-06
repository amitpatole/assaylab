"""Dashboard report: rendering, frontier, and XSS-safety of untrusted messages."""

from __future__ import annotations

from assaylab.dashboard import build_report, frontier
from assaylab.dashboard.render import render_report as _render
from assaylab.models import Outcome, TestRecord
from assaylab.rca.grade import grade_with_rca
from assaylab.select.engine import Candidate


def test_build_report_is_standalone_html() -> None:
    html = build_report(_csv())
    assert html.startswith("<!doctype html>")
    assert "assaylab report" in html
    assert "Confidence / speedup frontier" in html
    assert "— amitpatole" in html  # maker's mark
    assert "<svg" in html          # inline frontier chart


def test_report_escapes_untrusted_message() -> None:
    # A malicious test message must not become live markup in the report.
    evil = TestRecord(test_id="x", outcome=Outcome.FAIL, commit="c1", run_id="r1",
                      message="<script>alert('xss')</script> boom")
    report = grade_with_rca([evil])
    html = _render(report)
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html  # escaped


def test_frontier_is_monotonic_speedup_vs_confidence() -> None:
    cands = [Candidate(f"hot{i}", q=0.5, duration_s=1.0) for i in range(3)] + \
            [Candidate(f"cold{i}", q=0.001, duration_s=1.0) for i in range(30)]
    pts = frontier(cands)
    # Higher speedup should not come with higher confidence (it's a trade-off).
    ordered = sorted(pts, key=lambda p: p.speedup)
    confs = [p.confidence for p in ordered]
    assert confs == sorted(confs, reverse=True) or len(set(confs)) == 1


def _csv() -> str:
    lines = ["test_id,commit,run_id,verdict,duration,message"]
    for r in range(5):
        v = "fail" if r % 2 else "pass"
        lines.append(f"svc.Hot::t,c{r},r{r},{v},0.5,NullPointerException: boom")
        lines.append(f"svc.Cold::t,c{r},r{r},pass,0.3,")
    return "\n".join(lines)
