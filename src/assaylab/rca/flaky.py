"""Flaky-vs-real classification.

A failure signature is *flaky-leaning* when its affected tests behave
non-deterministically — the strongest evidence being a single commit that shows
both a pass and a failure (order-agnostic flakiness, à la iDFlakies), backed by
a high flip-rate across runs. Real failures are consistent at a given commit.

The heuristic here is always available; :func:`flaky_probability` optionally
defers to a learned model when one is supplied.
"""

from __future__ import annotations

from dataclasses import dataclass

from .features import TestStats


@dataclass
class FlakyVerdict:
    is_flaky: bool
    probability: float  # 0..1
    evidence: str


# Thresholds for the heuristic. Same-commit pass+fail is decisive on its own.
_FLIP_RATE_FLAKY = 0.34  # >1 flip per 3 runs suggests instability


def flaky_heuristic(tests: list[str], stats: dict[str, TestStats]) -> FlakyVerdict:
    relevant = [stats[t] for t in tests if t in stats]
    if not relevant:
        return FlakyVerdict(False, 0.0, "no history")

    if any(s.same_commit_flaky for s in relevant):
        return FlakyVerdict(True, 0.95, "same commit produced both pass and fail")

    max_flip = max(s.flip_rate for s in relevant)
    if max_flip >= _FLIP_RATE_FLAKY:
        # Map flip-rate in [_FLIP_RATE_FLAKY, 1] to probability in [0.6, 0.9].
        prob = 0.6 + 0.3 * min(1.0, (max_flip - _FLIP_RATE_FLAKY) / (1 - _FLIP_RATE_FLAKY))
        return FlakyVerdict(True, round(prob, 3), f"high flip-rate {max_flip:.2f} across runs")

    return FlakyVerdict(False, round(max_flip, 3), "consistent failures — looks real")


def flaky_probability(
    features: dict[str, float],
    tests: list[str],
    stats: dict[str, TestStats],
    model: object | None = None,
) -> FlakyVerdict:
    """Learned probability when ``model`` is given, else the heuristic."""
    if model is not None and hasattr(model, "predict_proba"):
        prob = float(model.predict_proba(features))  # type: ignore[attr-defined]
        return FlakyVerdict(prob >= 0.5, round(prob, 3), f"learned model p={prob:.2f}")
    return flaky_heuristic(tests, stats)
