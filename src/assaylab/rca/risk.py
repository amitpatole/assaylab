"""Per-test risk scoring and next-run failure forecasting.

Risk blends recency-weighted failure rate with instability (flip-rate): a test
that fails often *and* recently is high risk; a rarely-failing stable test is
low risk. ``forecast`` is the model's estimate that the test fails on its next
run, used later (P3) to bound the confidence lost when a test is skipped.
"""

from __future__ import annotations

from dataclasses import dataclass

from .features import TestStats

# Blend weights for the risk score (sum to 1).
_W_RECENCY = 0.7
_W_FLIP = 0.3


@dataclass
class Risk:
    test_id: str
    score: float       # 0..1 composite risk
    forecast: float    # 0..1 P(fail next run)
    fail_rate: float
    flip_rate: float


def test_risk(stats: TestStats) -> Risk:
    recency = stats.recency_weighted_fail_rate
    score = _W_RECENCY * recency + _W_FLIP * stats.flip_rate
    # Forecast leans on the most recent behavior; instability widens it toward 0.5.
    last_failed = bool(stats._ordered) and stats._ordered[-1][1].failed
    base = recency
    forecast = base + (0.5 - base) * stats.flip_rate if last_failed else base * (1 - stats.flip_rate)
    return Risk(
        test_id=stats.test_id,
        score=round(min(1.0, score), 4),
        forecast=round(min(1.0, max(0.0, forecast)), 4),
        fail_rate=round(stats.fail_rate, 4),
        flip_rate=round(stats.flip_rate, 4),
    )


def rank_risk(stats: dict[str, TestStats]) -> list[Risk]:
    """All tests ranked by descending risk."""
    return sorted((test_risk(s) for s in stats.values()), key=lambda r: -r.score)
