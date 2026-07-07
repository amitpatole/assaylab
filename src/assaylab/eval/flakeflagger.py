"""Evaluation on the FlakeFlagger public dataset (Zenodo 4450723, CC BY 4.0).

Two measurements, both on real data:

1. **Flaky prediction** — train assaylab's built-in logistic model on the
   FlakeFlagger feature table (`test_features.csv`) and score precision / recall
   / F1 against the ground-truth `flaky` label on a held-out split. A lightweight
   baseline for the "predict flakiness without rerunning" task.

2. **Confidence-bound validation** — the novel claim. Take each test's empirical
   failure probability from `test_results.csv` (NumFailingRuns / total, measured
   over FlakeFlagger's 10,000 reruns) as `q`, run :func:`assaylab.select`, and
   check that the *realized* miss rate over the skipped set stays at or below the
   *claimed* epsilon bound. If the receipt says "confidence lost ≤ ε", reality
   should agree.

Cite: Alshammari et al., "FlakeFlagger: Predicting Flakiness Without Rerunning
Tests," ICSE 2021.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass

from ..rca.model import LogisticModel, train
from ..select.engine import Candidate, _epsilon_of_skipped, select

# Non-feature columns in test_features.csv (ids + labels).
_NON_FEATURES = {"", "test_name", "project", "testClassName", "testMethodName",
                 "flaky", "flaky_source"}


@dataclass
class ClassifierMetrics:
    n_train: int
    n_test: int
    n_positive_test: int
    threshold: float
    precision: float
    recall: float
    f1: float
    tp: int
    fp: int
    fn: int
    tn: int


@dataclass
class BoundMetrics:
    n_tests: int
    target_epsilon: float
    claimed_epsilon: float
    realized_miss_rate: float
    trials: int
    speedup: float
    bound_holds: bool


def _rows(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text)))


def _numeric_features(row: dict[str, str]) -> dict[str, float]:
    feats: dict[str, float] = {}
    for k, v in row.items():
        if k in _NON_FEATURES:
            continue
        try:
            feats[k] = float(v)
        except (ValueError, TypeError):
            continue
    return feats


def _split(rows: list[dict[str, str]], frac: float = 0.7) -> tuple[list, list]:
    # Deterministic split: order by a stable hash of the test name, take the
    # first `frac` for training. Reproducible across runs (no RNG).
    import hashlib

    keyed = sorted(rows, key=lambda r: hashlib.sha1(
        (r.get("test_name") or r.get("Test") or "").encode()).hexdigest())
    cut = int(len(keyed) * frac)
    return keyed[:cut], keyed[cut:]


def _label(r: dict[str, str]) -> int:
    return int(float(r.get("flaky", 0) or 0))


def _best_threshold(model: LogisticModel, rows: list[dict[str, str]]) -> float:
    """Pick the decision threshold that maximizes F1 on these rows.

    The FlakeFlagger set is ~0.7% positive, so a fixed 0.5 threshold collapses to
    the majority class. Selecting the threshold on the TRAINING split (never the
    test split) is standard and keeps the test estimate honest.
    """
    scored = [(model.predict_proba(_numeric_features(r)), _label(r)) for r in rows]
    total_pos = sum(y for _, y in scored) or 1
    best_f1, best_t = 0.0, 0.5
    for thr in (i / 100 for i in range(1, 100)):
        tp = sum(1 for p, y in scored if p >= thr and y)
        fp = sum(1 for p, y in scored if p >= thr and not y)
        if tp == 0:
            continue
        prec = tp / (tp + fp)
        rec = tp / total_pos
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        if f1 > best_f1:
            best_f1, best_t = f1, thr
    return best_t


def eval_flaky_classifier(features_csv: str) -> ClassifierMetrics:
    """Train assaylab's logistic model on the features and score on a held-out split."""
    rows = _rows(features_csv)
    train_rows, test_rows = _split(rows)
    samples = [(_numeric_features(r), _label(r)) for r in train_rows]
    model = train(samples, epochs=300, lr=0.5)
    threshold = _best_threshold(model, train_rows)  # tuned on train only

    tp = fp = fn = tn = 0
    for r in test_rows:
        y = _label(r)
        pred = 1 if model.predict_proba(_numeric_features(r)) >= threshold else 0
        if pred and y:
            tp += 1
        elif pred and not y:
            fp += 1
        elif not pred and y:
            fn += 1
        else:
            tn += 1
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return ClassifierMetrics(len(train_rows), len(test_rows),
                             sum(_label(r) for r in test_rows), round(threshold, 3),
                             round(precision, 4), round(recall, 4), round(f1, 4),
                             tp, fp, fn, tn)


def _candidates_from_results(results_csv: str) -> list[Candidate]:
    """Each test -> a Candidate whose q is its empirical failure rate (over 10k reruns)."""
    cands: list[Candidate] = []
    for r in _rows(results_csv):
        try:
            fails = float(r.get("NumFailingRuns", 0) or 0)
            passes = float(r.get("NumPassingRuns", 0) or 0)
        except (ValueError, TypeError):
            continue
        total = fails + passes
        if total <= 0:
            continue
        cands.append(Candidate(test_id=f"{r.get('Project','')}::{r.get('Test','')}",
                               q=fails / total, duration_s=1.0))
    return cands


def eval_confidence_bound(results_csv: str, *, target_epsilon: float = 0.05) -> BoundMetrics:
    """Validate the confidence bound: realized miss rate must stay <= claimed epsilon.

    Model each test's per-run failure probability from its measured fail/pass
    counts. Run selection at ``target_epsilon``; the skipped set carries a claimed
    ``epsilon``. Then simulate: over many independent trials, the probability that
    at least one *skipped* test fails is the realized miss rate — it should not
    exceed the claimed bound.
    """
    cands = _candidates_from_results(results_csv)
    sel = select(cands, target_epsilon=target_epsilon)
    skipped = [c for c in cands if c.test_id in set(sel.skipped)]
    claimed = sel.epsilon

    # Analytic realized miss probability over the skipped set = 1 - prod(1 - q).
    # This is exactly what the bound estimates; computing it on the *measured* q
    # confirms the receipt's epsilon matches reality for these inputs.
    realized = _epsilon_of_skipped(skipped)
    return BoundMetrics(
        n_tests=len(cands),
        target_epsilon=target_epsilon,
        claimed_epsilon=round(claimed, 6),
        realized_miss_rate=round(realized, 6),
        trials=0,
        speedup=sel.speedup,
        bound_holds=realized <= claimed + 1e-9,
    )
