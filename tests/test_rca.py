"""RCA: root-cause categorization, flaky-vs-real, risk, learned model, grading."""

from __future__ import annotations

from agentsensory import Verdict

from assaylab.models import FailureSignature, Outcome, TestRecord
from assaylab.rca import (
    LogisticModel,
    RootCause,
    categorize,
    grade_with_rca,
    history_stats,
    rank_risk,
    train,
)
from assaylab.rca.features import signature_features
from assaylab.rca.flaky import flaky_heuristic


def _sig(exc: str, msg: str, tests: list[str]) -> FailureSignature:
    return FailureSignature(signature_id="s", template=f"{exc} {msg}", exception_type=exc,
                            tests=tests, count=len(tests), sample_message=msg)


# ---- root cause -----------------------------------------------------------

def test_categorize_null_deref() -> None:
    c = categorize(_sig("NullPointerException", "card was null", ["t"]))
    assert c.cause == RootCause.NULL_DEREF
    assert c.confidence >= 0.8


def test_categorize_timeout_and_dependency() -> None:
    assert categorize(_sig("", "operation timed out after 30s", ["t"])).cause == RootCause.TIMEOUT
    assert categorize(_sig("ImportError", "No module named 'foo'", ["t"])).cause == RootCause.DEPENDENCY


def test_categorize_unknown_when_no_rule() -> None:
    assert categorize(_sig("", "weird gibberish xyzzy", ["t"])).cause == RootCause.UNKNOWN


# ---- flaky detection ------------------------------------------------------

def _runs(test_id: str, outcomes: list[tuple[str, Outcome]]) -> list[TestRecord]:
    return [TestRecord(test_id=test_id, outcome=oc, commit=commit, run_id=f"r{i}", message="boom")
            for i, (commit, oc) in enumerate(outcomes)]


def test_same_commit_pass_and_fail_is_flaky() -> None:
    recs = _runs("t", [("c1", Outcome.PASS), ("c1", Outcome.FAIL)])
    stats = history_stats(recs)
    v = flaky_heuristic(["t"], stats)
    assert v.is_flaky and v.probability >= 0.9


def test_consistent_failures_look_real() -> None:
    recs = _runs("t", [("c1", Outcome.FAIL), ("c2", Outcome.FAIL), ("c3", Outcome.FAIL)])
    stats = history_stats(recs)
    assert not flaky_heuristic(["t"], stats).is_flaky


def test_high_flip_rate_is_flaky() -> None:
    recs = _runs("t", [("c1", Outcome.PASS), ("c2", Outcome.FAIL),
                       ("c3", Outcome.PASS), ("c4", Outcome.FAIL)])
    stats = history_stats(recs)
    assert flaky_heuristic(["t"], stats).is_flaky


# ---- risk -----------------------------------------------------------------

def test_risk_ranks_recent_persistent_failures_higher() -> None:
    recs = _runs("bad", [("c1", Outcome.FAIL)] * 4) + _runs("ok", [("c1", Outcome.PASS)] * 4)
    ranked = rank_risk(history_stats(recs))
    assert ranked[0].test_id == "bad"
    assert ranked[0].score > ranked[-1].score


# ---- learned model --------------------------------------------------------

def test_logistic_model_learns_and_json_roundtrips() -> None:
    # flaky iff same_commit flag is on; model should learn that separation.
    samples = []
    for _ in range(30):
        samples.append(({"any_same_commit_flaky": 1.0, "mean_flip_rate": 0.5}, 1))
        samples.append(({"any_same_commit_flaky": 0.0, "mean_flip_rate": 0.0}, 0))
    model = train(samples)
    assert model.predict_proba({"any_same_commit_flaky": 1.0, "mean_flip_rate": 0.5}) > 0.5
    assert model.predict_proba({"any_same_commit_flaky": 0.0, "mean_flip_rate": 0.0}) < 0.5
    # JSON round-trip preserves predictions exactly.
    restored = LogisticModel.from_json(model.to_json())
    feats = {"any_same_commit_flaky": 1.0, "mean_flip_rate": 0.5}
    assert abs(restored.predict_proba(feats) - model.predict_proba(feats)) < 1e-9


def test_model_rejects_wrong_schema() -> None:
    import pytest

    with pytest.raises(ValueError):
        LogisticModel.from_json('{"schema": "evil/9", "feature_names": [], "weights": [], "bias": 0}')


# ---- RCA grading ----------------------------------------------------------

def test_grade_all_flaky_is_warn_not_fail() -> None:
    recs = _runs("t", [("c1", Outcome.PASS), ("c1", Outcome.FAIL)])  # same-commit flaky
    report = grade_with_rca(recs)
    assert report.verdict == Verdict.WARN
    assert report.issues[0].detail["flaky"] is True


def test_grade_real_failure_is_fail_with_cause() -> None:
    recs = [TestRecord(test_id="t", outcome=Outcome.ERROR, commit="c1", run_id="r0",
                       message="NullPointerException: null", stacktrace="")]
    report = grade_with_rca(recs)
    assert report.verdict == Verdict.FAIL
    assert report.issues[0].detail["root_cause"] == RootCause.NULL_DEREF.value


def test_signature_features_shape() -> None:
    recs = _runs("t", [("c1", Outcome.FAIL), ("c2", Outcome.PASS)])
    feats = signature_features(["t"], history_stats(recs))
    assert set(feats) >= {"n_tests", "mean_fail_rate", "mean_flip_rate", "any_same_commit_flaky"}
