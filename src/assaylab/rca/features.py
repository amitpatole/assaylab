"""History-aware feature extraction.

Turns a flat list of :class:`TestRecord`s (many runs of many tests) into
per-test statistics and per-signature feature vectors that the root-cause
categorizer, the flaky classifier, and the learned model all consume.

Run order is taken from ``run_id`` (lexicographic) so flip-rate is well defined
even when timestamps are absent — deterministic and reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..models import Outcome, TestRecord


@dataclass
class TestStats:
    """Aggregate history for a single test across runs."""

    test_id: str
    runs: int = 0
    fails: int = 0
    flips: int = 0  # pass<->fail transitions across ordered runs
    # commit -> set of distinct outcomes seen at that commit (for same-commit flakiness)
    _by_commit: dict[str, set[str]] = field(default_factory=dict)
    _ordered: list[tuple[str, Outcome]] = field(default_factory=list)

    @property
    def fail_rate(self) -> float:
        return self.fails / self.runs if self.runs else 0.0

    @property
    def flip_rate(self) -> float:
        return self.flips / (self.runs - 1) if self.runs > 1 else 0.0

    @property
    def same_commit_flaky(self) -> bool:
        """True if any single commit shows BOTH a pass and a failure (order-agnostic flakiness)."""
        for outcomes in self._by_commit.values():
            if "pass" in outcomes and ("fail" in outcomes or "error" in outcomes):
                return True
        return False

    @property
    def recency_weighted_fail_rate(self) -> float:
        """Failure rate weighting recent runs more (linear ramp)."""
        if not self._ordered:
            return 0.0
        num = den = 0.0
        n = len(self._ordered)
        for i, (_commit, oc) in enumerate(self._ordered):
            w = (i + 1) / n  # later runs weigh more
            den += w
            if oc.failed:
                num += w
        return num / den if den else 0.0


def history_stats(records: list[TestRecord]) -> dict[str, TestStats]:
    """Aggregate per-test stats. Records are processed in ``run_id`` order."""
    ordered = sorted(records, key=lambda r: (r.test_id, r.run_id))
    stats: dict[str, TestStats] = {}
    for rec in ordered:
        if rec.outcome == Outcome.SKIP:
            continue
        st = stats.get(rec.test_id)
        if st is None:
            st = TestStats(test_id=rec.test_id)
            stats[rec.test_id] = st
        if st._ordered:
            prev = st._ordered[-1][1]
            if prev.failed != rec.outcome.failed:
                st.flips += 1
        st.runs += 1
        if rec.outcome.failed:
            st.fails += 1
        st._ordered.append((rec.commit or rec.run_id, rec.outcome))
        st._by_commit.setdefault(rec.commit or "", set()).add(rec.outcome.value)
    return stats


def signature_features(
    tests: list[str],
    stats: dict[str, TestStats],
) -> dict[str, float]:
    """Feature vector for a signature, aggregated over its affected tests.

    Deliberately small and interpretable — these are the inputs to both the
    heuristic classifier and the learned flaky model.
    """
    relevant = [stats[t] for t in tests if t in stats]
    if not relevant:
        return {
            "n_tests": float(len(tests)),
            "mean_fail_rate": 1.0,
            "mean_flip_rate": 0.0,
            "max_flip_rate": 0.0,
            "any_same_commit_flaky": 0.0,
            "mean_recency_fail_rate": 1.0,
        }
    n = len(relevant)
    return {
        "n_tests": float(len(tests)),
        "mean_fail_rate": sum(s.fail_rate for s in relevant) / n,
        "mean_flip_rate": sum(s.flip_rate for s in relevant) / n,
        "max_flip_rate": max(s.flip_rate for s in relevant),
        "any_same_commit_flaky": 1.0 if any(s.same_commit_flaky for s in relevant) else 0.0,
        "mean_recency_fail_rate": sum(s.recency_weighted_fail_rate for s in relevant) / n,
    }
