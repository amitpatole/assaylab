"""Grading records into an agentsensory Report + Handoff round-trip."""

from __future__ import annotations

from agentsensory import Handoff, NextAction, ReportBase, Verdict

from assaylab.core import analyze, grade_records, to_handoff
from assaylab.models import IssueKind, Outcome, TestRecord


def _rec(test_id: str, outcome: Outcome, msg: str = "") -> TestRecord:
    return TestRecord(test_id=test_id, outcome=outcome, message=msg)


def test_all_pass_is_pass_verdict() -> None:
    r = grade_records([_rec("a", Outcome.PASS), _rec("b", Outcome.PASS)])
    assert r.verdict == Verdict.PASS
    assert not r.issues


def test_failure_produces_fail_and_grounded_issue() -> None:
    r = grade_records([_rec("a", Outcome.PASS), _rec("b", Outcome.FAIL, "AssertionError: nope")])
    assert r.verdict == Verdict.FAIL
    assert len(r.issues) == 1
    issue = r.issues[0]
    assert issue.kind == IssueKind.FAILURE_SIGNATURE.value
    # grounding lives in detail
    assert issue.detail["tests"] == ["b"]
    assert issue.detail["signature_id"]


def test_report_is_contract_valid() -> None:
    r = grade_records([_rec("b", Outcome.FAIL, "boom")])
    assert isinstance(r, ReportBase)
    # round-trips through the shared JSON schema
    assert ReportBase.model_validate(r.model_dump())


def test_baseline_flags_new_failures() -> None:
    baseline = [_rec("a", Outcome.FAIL, "OldError: known")]
    from assaylab.core import cluster

    base_ids = {s.signature_id for s in cluster(baseline)}
    records = [_rec("a", Outcome.FAIL, "OldError: known"), _rec("b", Outcome.FAIL, "BrandNewError: x")]
    r = grade_records(records, baseline_ids=base_ids)
    kinds = {i.kind for i in r.issues}
    assert IssueKind.NEW_FAILURE.value in kinds
    assert IssueKind.FAILURE_SIGNATURE.value in kinds


def test_handoff_roundtrip() -> None:
    r = grade_records([_rec("b", Outcome.FAIL, "boom")])
    h = to_handoff(r)
    assert isinstance(h, Handoff)
    assert h.perceived == Verdict.FAIL
    assert h.next_action == NextAction.REVISE
    assert h.todo  # at least one actionable item


async def test_analyze_end_to_end() -> None:
    junit = '<testsuite name="s"><testcase classname="s.A" name="x"><failure message="E: boom"/></testcase></testsuite>'
    r = await analyze(junit, backend="junit")
    assert r.verdict == Verdict.FAIL
