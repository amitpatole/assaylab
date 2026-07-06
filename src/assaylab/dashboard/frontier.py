"""The confidence/speedup frontier — assaylab's headline result.

Sweeps the selection target and, for each point, records how much test time is
saved (speedup) against the confidence retained (1 - epsilon). Rendered as a
dependency-free inline SVG so the report is fully self-contained.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..select.engine import Candidate, select

# Confidence targets to sweep (epsilon = confidence lost).
_SWEEP = [0.5, 0.3, 0.2, 0.1, 0.05, 0.02, 0.01, 0.005, 0.001, 0.0]


@dataclass
class FrontierPoint:
    target_epsilon: float
    epsilon: float
    confidence: float
    speedup: float
    n_selected: int
    n_total: int


def frontier(candidates: list[Candidate]) -> list[FrontierPoint]:
    """Selection outcome across a sweep of confidence targets."""
    pts: list[FrontierPoint] = []
    n = len(candidates)
    for target in _SWEEP:
        sel = select(candidates, target_epsilon=target)
        pts.append(FrontierPoint(
            target_epsilon=target,
            epsilon=sel.epsilon,
            confidence=sel.confidence,
            speedup=sel.speedup,
            n_selected=len(sel.selected),
            n_total=n,
        ))
    return pts


def frontier_svg(points: list[FrontierPoint], *, width: int = 640, height: int = 320,
                 accent: str = "#3c6b4c", ink: str = "#1b1a17", muted: str = "#6b6862",
                 rule: str = "#e3ded4") -> str:
    """Render the speedup (x) vs confidence (y) frontier as an inline SVG."""
    if not points:
        return "<p>no frontier data</p>"
    pad_l, pad_r, pad_t, pad_b = 56, 20, 20, 44
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b

    speedups = [p.speedup for p in points]
    max_speedup = max(speedups + [1.0])
    # x = speedup in [1, max]; y = confidence in [min_conf, 1].
    min_conf = min(p.confidence for p in points)
    y_lo = min(min_conf, 0.9)  # keep the interesting band visible

    def x_of(sp: float) -> float:
        return pad_l + (sp - 1.0) / (max_speedup - 1.0 or 1.0) * plot_w

    def y_of(conf: float) -> float:
        return pad_t + (1.0 - (conf - y_lo) / (1.0 - y_lo or 1.0)) * plot_h

    ordered = sorted(points, key=lambda p: p.speedup)
    path = " ".join(
        f"{'M' if i == 0 else 'L'}{x_of(p.speedup):.1f},{y_of(p.confidence):.1f}"
        for i, p in enumerate(ordered)
    )
    dots = "".join(
        f'<circle cx="{x_of(p.speedup):.1f}" cy="{y_of(p.confidence):.1f}" r="3.5" '
        f'fill="{accent}"><title>{p.speedup:.2f}x speedup, '
        f'{p.confidence*100:.2f}% confidence ({p.n_selected}/{p.n_total} tests)</title></circle>'
        for p in ordered
    )
    # Axis ticks.
    x_axis = (f'<line x1="{pad_l}" y1="{pad_t+plot_h}" x2="{pad_l+plot_w}" y2="{pad_t+plot_h}" '
              f'stroke="{rule}"/>')
    y_axis = f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+plot_h}" stroke="{rule}"/>'
    x_label = (f'<text x="{pad_l+plot_w/2}" y="{height-10}" text-anchor="middle" '
               f'fill="{muted}" font-size="12">test-time speedup →</text>')
    y_label = (f'<text x="14" y="{pad_t+plot_h/2}" text-anchor="middle" fill="{muted}" '
               f'font-size="12" transform="rotate(-90 14 {pad_t+plot_h/2})">confidence retained →</text>')
    y_hi = f'<text x="{pad_l-8}" y="{y_of(1.0)+4:.1f}" text-anchor="end" fill="{muted}" font-size="11">100%</text>'
    y_low = (f'<text x="{pad_l-8}" y="{y_of(y_lo)+4:.1f}" text-anchor="end" fill="{muted}" '
             f'font-size="11">{y_lo*100:.0f}%</text>')

    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" '
        f'aria-label="confidence vs speedup frontier" xmlns="http://www.w3.org/2000/svg">'
        f'{x_axis}{y_axis}{x_label}{y_label}{y_hi}{y_low}'
        f'<path d="{path}" fill="none" stroke="{accent}" stroke-width="2"/>{dots}</svg>'
    )
