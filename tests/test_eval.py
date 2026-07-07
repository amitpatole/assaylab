"""Evaluation harness (FlakeFlagger adapters) on synthetic inputs.

The real dataset (Zenodo 4450723) is fetched on demand and not vendored, so CI
exercises the harness on small deterministic fixtures.
"""

from __future__ import annotations

from assaylab.eval import eval_confidence_bound, eval_flaky_classifier


def test_confidence_bound_holds_on_synthetic_results() -> None:
    # A few high-failure-rate tests + many stable ones. Selection should skip the
    # stable ones and the realized miss rate must stay within the claimed bound.
    rows = ["Project,Test,IsFlaky,NumFailingRuns,NumPassingRuns"]
    for i in range(3):
        rows.append(f"p,hot{i},1,5000,5000")   # q = 0.5
    for i in range(60):
        rows.append(f"p,cold{i},0,1,9999")      # q ~ 1e-4
    bm = eval_confidence_bound("\n".join(rows), target_epsilon=0.05)
    assert bm.n_tests == 63
    assert bm.bound_holds                       # realized <= claimed
    assert bm.speedup > 1.0                     # dropped the cold tests
    assert bm.claimed_epsilon <= 0.05 + 1e-6


def test_flaky_classifier_learns_a_separable_signal() -> None:
    # A feature that cleanly separates flaky from non-flaky -> non-trivial F1.
    header = ",test_name,project,flaky,signal"
    rows = [header]
    for i in range(40):
        rows.append(f"{i},pos{i},p,1,{9 + (i % 3)}")     # flaky, high signal
    for i in range(40):
        rows.append(f"{i+40},neg{i},p,0,{0 + (i % 3)}")  # non-flaky, low signal
    cm = eval_flaky_classifier("\n".join(rows))
    assert cm.n_train > 0 and cm.n_test > 0
    assert cm.f1 > 0.5                          # the signal is learnable
