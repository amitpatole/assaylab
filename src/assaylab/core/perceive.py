"""Distill a :class:`Report` into an agentsensory :class:`Handoff` for the brain."""

from __future__ import annotations

from agentsensory import Handoff

from ..config import Settings
from ..models import Report
from .analyze import analyze


def to_handoff(report: Report) -> Handoff:
    """Distill a graded report into the brain-facing signal."""
    return Handoff.from_report(report)


async def perceive(
    source: str,
    *,
    backend: str | None = None,
    baseline: str | None = None,
    settings: Settings | None = None,
) -> Handoff:
    report = await analyze(source, backend=backend, baseline=baseline, settings=settings or Settings())
    return to_handoff(report)
