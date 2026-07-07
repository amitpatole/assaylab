"""Attested test-selection: confidence-bound math, receipts, tamper-detection."""

from __future__ import annotations

from assaylab.attest import Receipt, hash_ids
from assaylab.select import Candidate, select
from assaylab.select.service import attest, candidates_hash


def _cands() -> list[Candidate]:
    # Three risky tests + many near-zero-risk ones.
    risky = [Candidate(f"hot{i}", q=0.5, duration_s=1.0) for i in range(3)]
    cold = [Candidate(f"cold{i}", q=0.001, duration_s=1.0) for i in range(50)]
    return risky + cold


# ---- selection math -------------------------------------------------------

def test_target_epsilon_keeps_high_risk_drops_low() -> None:
    sel = select(_cands(), target_epsilon=0.05)
    # The three hot tests must be kept (each q=0.5 dominates epsilon).
    assert {"hot0", "hot1", "hot2"} <= set(sel.selected)
    assert sel.epsilon <= 0.05
    assert sel.speedup > 1.0  # dropped many cold tests


def test_epsilon_is_zero_when_all_selected() -> None:
    sel = select(_cands(), target_epsilon=0.0)
    assert sel.epsilon == 0.0
    assert not sel.skipped


def test_time_budget_limits_selection() -> None:
    sel = select(_cands(), time_budget_s=3.0)
    assert sel.time_selected_s <= 3.0
    # highest value-density (the q=0.5 tests) are kept first
    assert {"hot0", "hot1", "hot2"} <= set(sel.selected)


def test_forced_tests_always_kept() -> None:
    cands = [Candidate("changed", q=0.0, duration_s=1.0, forced=True),
             Candidate("other", q=0.9, duration_s=1.0)]
    sel = select(cands, time_budget_s=0.0)  # zero budget, but forced survives
    assert "changed" in sel.selected


def test_more_confidence_costs_more_time() -> None:
    strict = select(_cands(), target_epsilon=0.001)
    loose = select(_cands(), target_epsilon=0.2)
    assert strict.time_selected_s >= loose.time_selected_s
    assert strict.epsilon <= loose.epsilon


# ---- receipts -------------------------------------------------------------

def test_receipt_signs_and_verifies() -> None:
    key = b"0" * 32
    r = Receipt(epsilon=0.05, confidence=0.95).sign(key)
    assert r.verify(key)


def test_full_attest_then_verify_with_env_key(monkeypatch) -> None:
    monkeypatch.setenv("ASSAYLAB_SIGNING_KEY", "hex:" + "0123456789abcdef" * 4)  # varied 32B
    sel = select(_cands(), target_epsilon=0.05)
    rec = attest(sel, _cands(), created_ts=1234.0)
    from assaylab.select.service import verify_receipt

    assert verify_receipt(rec)
    assert rec.epsilon == sel.epsilon  # receipt binds the actual bound
    assert rec.n_selected == len(sel.selected)


def test_tampering_breaks_signature() -> None:
    key = b"k" * 32
    rec = Receipt(epsilon=0.01, confidence=0.99, n_selected=5).sign(key)
    assert rec.verify(key)
    rec.epsilon = 0.5  # forge a better-looking bound
    assert not rec.verify(key)  # signature no longer matches the body


def test_wrong_key_fails_verification() -> None:
    rec = Receipt(epsilon=0.01).sign(b"a" * 32)
    assert not rec.verify(b"b" * 32)


def test_candidates_hash_is_stable_and_binds_inputs() -> None:
    c = _cands()
    h1 = candidates_hash(c)
    assert h1 == candidates_hash(list(reversed(c)))  # order-independent
    c2 = c[:]
    c2[0] = Candidate(c2[0].test_id, q=0.99, duration_s=1.0)  # change a q input
    assert candidates_hash(c2) != h1  # hash binds the q values


def test_hash_ids_order_independent() -> None:
    assert hash_ids(["b", "a"]) == hash_ids(["a", "b"])


# ---- red-team round-1 fixes -----------------------------------------------

def test_duplicate_test_ids_do_not_inflate_epsilon() -> None:
    # L7: two rows for the same test must count once, not twice.
    dup = select([Candidate("A", q=0.9, duration_s=1.0), Candidate("A", q=0.9, duration_s=1.0)],
                 target_epsilon=1.0)  # skip everything
    single = select([Candidate("A", q=0.9, duration_s=1.0)], target_epsilon=1.0)
    assert abs(dup.epsilon - single.epsilon) < 1e-9  # ~0.9, not ~0.99


def test_epsilon_is_rounded_up_not_understated() -> None:
    # L6: a tiny skipped q must not report epsilon 0.0 / confidence 1.0.
    sel = select([Candidate("t", q=4e-7, duration_s=1.0)], target_epsilon=0.5)
    assert sel.epsilon > 0.0
    assert abs(sel.confidence - (1.0 - sel.epsilon)) < 1e-12  # derived, consistent


def test_receipt_refuses_non_finite_floats() -> None:
    # Round-2 Finding 1: inf/nan serialize differently in json.dumps vs pydantic,
    # which would split signed vs stored bytes — the receipt must reject them.
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Receipt(epsilon=float("inf"))
    with pytest.raises(ValidationError):
        Receipt(time_all_s=float("nan"))


def test_ingest_sanitizes_non_finite_duration() -> None:
    from assaylab.core import ingest

    recs = ingest('<testsuite name="s"><testcase classname="s.A" name="x" time="inf"/></testsuite>',
                  backend="junit")
    assert recs[0].duration_s == 0.0  # inf rejected at ingest


def test_receipt_carries_a_nonce(monkeypatch) -> None:
    # M4: each receipt is unique (uniqueness anchor bound by the signature).
    monkeypatch.setenv("ASSAYLAB_SIGNING_KEY", "hex:" + "0123456789abcdef" * 4)
    sel = select(_cands(), target_epsilon=0.05)
    r1 = attest(sel, _cands(), created_ts=1.0)
    r2 = attest(sel, _cands(), created_ts=1.0)
    assert r1.nonce and r2.nonce and r1.nonce != r2.nonce
    assert r1.signature != r2.signature  # nonce is inside the signed body


def test_verify_reproduction_confirms_genuine_bound(monkeypatch) -> None:
    from assaylab.select.service import verify_reproduction

    cands = _cands()
    sel = select(cands, target_epsilon=0.05)
    rec = attest(sel, cands, created_ts=1.0)
    ok, reason = verify_reproduction(rec, cands)
    assert ok, reason


def test_verify_reproduction_catches_forged_bound() -> None:
    from assaylab.select.service import verify_reproduction

    cands = _cands()
    sel = select(cands, target_epsilon=0.05)
    rec = attest(sel, cands, created_ts=1.0)
    rec.epsilon = 0.0001  # forge a tighter bound than the inputs actually yield
    ok, _ = verify_reproduction(rec, cands)
    assert not ok  # recomputation from inputs exposes the lie


def test_verify_reproduction_detects_swapped_inputs() -> None:
    from assaylab.select.service import verify_reproduction

    cands = _cands()
    sel = select(cands, target_epsilon=0.05)
    rec = attest(sel, cands, created_ts=1.0)
    tampered = cands + [Candidate("extra", q=0.9, duration_s=1.0)]
    ok, reason = verify_reproduction(rec, tampered)
    assert not ok and "inputs" in reason
