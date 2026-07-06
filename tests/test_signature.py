"""Failure-signature normalization + clustering."""

from __future__ import annotations

from assaylab.core import cluster, fingerprint, normalize
from assaylab.models import Outcome, TestRecord


def _fail(test_id: str, message: str, stack: str = "") -> TestRecord:
    return TestRecord(test_id=test_id, outcome=Outcome.ERROR, message=message, stacktrace=stack)


def test_normalize_strips_incidental_variation() -> None:
    a = normalize("null at 0x7ffa12 line 88 at 2024-01-02T03:04:05Z")
    b = normalize("null at 0x9b3c01 line 140 at 2025-06-07T08:09:10Z")
    assert a == b  # addresses, numbers, timestamps collapse to placeholders


def test_same_root_different_addresses_cluster_together() -> None:
    stack = 'File "checkout/pay.py", line {n}, in charge\n    gateway.submit(card.token)'
    r1 = _fail("PaymentTest::charge", "NullPointerException: card was null at 0x7ffa12",
               stack.format(n=140))
    r2 = _fail("RefundTest::refund", "NullPointerException: card was null at 0x9b3c01",
               stack.format(n=141))
    sigs = cluster([r1, r2])
    assert len(sigs) == 1
    assert sigs[0].count == 2
    assert set(sigs[0].tests) == {"PaymentTest::charge", "RefundTest::refund"}
    assert sigs[0].exception_type == "NullPointerException"


def test_distinct_roots_stay_separate() -> None:
    r1 = _fail("t1", "AssertionError: expected 42 but got 41")
    r2 = _fail("t2", "NullPointerException: card was null")
    sigs = cluster([r1, r2])
    assert len(sigs) == 2


def test_passing_records_have_no_signature() -> None:
    ok = TestRecord(test_id="t", outcome=Outcome.PASS)
    assert cluster([ok]) == []


def test_fingerprint_is_stable_and_deterministic() -> None:
    r = _fail("t", "boom at 0xdead")
    assert fingerprint(r)[0] == fingerprint(r)[0]
    assert len(fingerprint(r)[0]) == 12
