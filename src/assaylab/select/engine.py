"""Test-selection engine with a verifiable confidence bound.

Each candidate test ``t`` has a detection probability ``q_t`` — the modelled
chance it fails (catches a regression) on this run, estimated from history
(P2 forecast). If we run a subset ``S`` and skip ``U = All \\ S``, the
probability that *at least one* skipped test would have failed is

    epsilon = 1 - prod_{t in U} (1 - q_t)

under an independence assumption. ``epsilon`` is the **confidence lost** by
skipping — an upper-bound proxy for the chance we miss a regression the suite
would have caught. Selection keeps the highest value-density tests
(``q_t`` per second) until either ``epsilon <= target_epsilon`` or the
``time_budget_s`` is exhausted; the achieved ``epsilon`` is always reported.

Honest limits (stated, not hidden): independence of failures, ``q_t``
stationarity, and coverage only of regression classes seen historically. These
are the receipt's residual assumptions, not guarantees.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from pydantic import BaseModel, Field

from ..config import MAX_TEST_DURATION_S


@dataclass
class Candidate:
    test_id: str
    q: float           # detection probability in [0, 1]
    duration_s: float = 1.0
    forced: bool = False  # always keep (e.g. directly touched by a code change)

    @property
    def clamped_q(self) -> float:
        if not math.isfinite(self.q):  # inf/nan from an untrusted corpus -> treat as no signal
            return 0.0
        return min(1.0, max(0.0, self.q))

    @property
    def clamped_duration(self) -> float:
        # Finite, non-negative, magnitude-bounded — so aggregate durations can't
        # overflow to inf/nan in the selection math (R3-1).
        d = self.duration_s
        if not math.isfinite(d) or d < 0:
            return 0.0
        return min(d, MAX_TEST_DURATION_S)


class Selection(BaseModel):
    selected: list[str] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list)
    epsilon: float = 0.0
    confidence: float = 1.0
    time_selected_s: float = 0.0
    time_all_s: float = 0.0
    speedup: float = 1.0
    objective: str = ""
    target_epsilon: float | None = None
    time_budget_s: float | None = None


def _epsilon_of_skipped(skipped: list[Candidate]) -> float:
    """1 - prod(1 - q) over skipped tests."""
    retained = 1.0
    for c in skipped:
        retained *= (1.0 - c.clamped_q)
    return 1.0 - retained


def _safe_speedup(time_all: float, time_used: float) -> float:
    """Total, finite speedup — never inf/nan even on pathological durations."""
    if time_used <= 0:
        return 1.0
    sp = round(time_all / time_used, 4)
    return sp if math.isfinite(sp) else 1.0


def select(
    candidates: list[Candidate],
    *,
    target_epsilon: float | None = None,
    time_budget_s: float | None = None,
) -> Selection:
    """Choose a subset to run under a confidence target and/or a time budget.

    Exactly one of ``target_epsilon`` / ``time_budget_s`` should be the primary
    driver; if both are given, selection stops as soon as *either* is satisfied
    (target met) or violated (budget spent).
    """
    if not candidates:
        return Selection(objective="empty")
    # Dedupe by test_id, keeping the highest-detection copy (closes L7: duplicate
    # ids double-counting into epsilon). One row per distinct test.
    by_id: dict[str, Candidate] = {}
    for c in candidates:
        prev = by_id.get(c.test_id)
        if prev is None or c.clamped_q > prev.clamped_q:
            by_id[c.test_id] = c
    candidates = list(by_id.values())
    time_all = sum(c.clamped_duration for c in candidates)

    # Order: forced first, then by value density q/duration (desc). Keeping a
    # high-q, cheap test removes the most epsilon per second.
    def density(c: Candidate) -> float:
        return c.clamped_q / c.clamped_duration if c.clamped_duration > 0 else c.clamped_q

    ordered = sorted(candidates, key=lambda c: (not c.forced, -density(c), c.test_id))

    # Track the epsilon over the not-yet-selected set INCREMENTALLY: a running
    # product of (1 - q) plus a separate count of zero factors (q == 1, which
    # would zero the product and can't be divided back out). Selecting a test
    # removes its factor in O(1). This makes the loop O(n log n) after the sort
    # instead of the previous O(n^3) rebuild — an untrusted corpus can no longer
    # drive super-quadratic compute (R4-1).
    zero_count = sum(1 for c in candidates if c.clamped_q >= 1.0)
    prod_nonzero = 1.0
    for c in candidates:
        if c.clamped_q < 1.0:
            prod_nonzero *= (1.0 - c.clamped_q)

    def _current_epsilon() -> float:
        return 1.0 - (0.0 if zero_count else prod_nonzero)

    selected: list[Candidate] = []
    sel_ids: set[str] = set()
    time_used = 0.0
    for c in ordered:
        # Target met (over everything not yet selected) -> stop; forced kept.
        if target_epsilon is not None and not c.forced and _current_epsilon() <= target_epsilon:
            break
        # Respect the time budget (forced tests are kept regardless).
        if (time_budget_s is not None and not c.forced
                and time_used + c.clamped_duration > time_budget_s):
            continue
        selected.append(c)
        sel_ids.add(c.test_id)
        time_used += c.clamped_duration
        if c.clamped_q >= 1.0:
            zero_count -= 1
        else:
            prod_nonzero /= (1.0 - c.clamped_q)

    skipped = [c for c in candidates if c.test_id not in sel_ids]
    # Round epsilon UP (conservative: never understate the confidence lost), and
    # derive confidence from the reported epsilon so the two can't disagree (L6).
    eps_raw = _epsilon_of_skipped(skipped)
    eps = math.ceil(eps_raw * 1_000_000) / 1_000_000
    objective = ("target_epsilon" if target_epsilon is not None
                 else "time_budget" if time_budget_s is not None else "all")
    return Selection(
        selected=sorted(sel_ids),
        skipped=sorted(c.test_id for c in skipped),
        epsilon=eps,
        confidence=round(1.0 - eps, 6),
        time_selected_s=round(time_used, 4),
        time_all_s=round(time_all, 4),
        speedup=_safe_speedup(time_all, time_used),
        objective=objective,
        target_epsilon=target_epsilon,
        time_budget_s=time_budget_s,
    )
