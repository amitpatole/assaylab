"""Assemble a full dashboard report from a source."""

from __future__ import annotations

from ..config import Settings
from ..core.ingest import ingest
from ..rca.features import history_stats
from ..rca.grade import grade_with_rca
from ..rca.risk import rank_risk
from ..select.service import candidates_from_history
from .frontier import frontier
from .render import render_report


def build_report(
    source: str,
    *,
    backend: str | None = None,
    title: str = "assaylab report",
    settings: Settings | None = None,
) -> str:
    """Ingest a source and render the full Warm Paper HTML report (RCA + risk + frontier)."""
    settings = settings or Settings()
    records = ingest(source, backend=backend, settings=settings)
    report = grade_with_rca(records, backend=backend or "inferred")
    ranked = rank_risk(history_stats(records))
    candidates = candidates_from_history(records)
    points = frontier(candidates) if candidates else []
    return render_report(report, ranked=ranked, frontier_points=points,
                         title=title, source_label="")
