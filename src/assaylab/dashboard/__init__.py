"""The validation-intelligence dashboard: a self-contained Warm Paper HTML report."""

from __future__ import annotations

from .frontier import FrontierPoint, frontier, frontier_svg
from .render import render_report
from .service import build_report

__all__ = ["FrontierPoint", "frontier", "frontier_svg", "render_report", "build_report"]
