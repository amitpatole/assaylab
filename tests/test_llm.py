"""LLM-assisted test-gen / self-heal — proposals, gating, provenance."""

from __future__ import annotations

from assaylab.core import cluster
from assaylab.llm import (
    Proposal,
    ProposalKind,
    evaluate_proposal,
    propose_heal,
    propose_test,
    resolve_provider,
)
from assaylab.models import FailureSignature, Outcome, TestRecord

_MSG = "NullPointerException: card was null"
_STACK = 'File "checkout/pay.py", line 140, in charge'


def _sig() -> FailureSignature:
    # Derive from a real record so signature_id is the TRUE fingerprint — the
    # gate now requires a reproduction to match this exact signature.
    rec = TestRecord(test_id="svc.Payment::test_charge", outcome=Outcome.ERROR,
                     message=_MSG, stacktrace=_STACK)
    return cluster([rec])[0]


def test_template_provider_is_available_keyfree() -> None:
    p = resolve_provider("template")
    assert p.available()
    assert p.name == "template"


def test_propose_test_produces_dry_run_proposal() -> None:
    proposal = propose_test(_sig(), provider="template", created_ts=1.0)
    assert proposal.kind == ProposalKind.TEST_GENERATION
    assert proposal.applied is False          # invariant: never applied
    assert proposal.provider == "template"
    assert proposal.prompt_sha                # provenance recorded
    assert proposal.acceptance["check"] == "reproduces"
    assert proposal.acceptance["target_test"] == "svc.Payment::test_charge"
    assert "pytest" in proposal.content


def test_propose_heal_produces_dry_run_proposal() -> None:
    proposal = propose_heal(_sig(), provider="template", created_ts=1.0)
    assert proposal.kind == ProposalKind.SELF_HEAL
    assert proposal.applied is False
    assert proposal.acceptance["check"] == "no_longer_fails"


def test_proposal_json_roundtrips() -> None:
    p = propose_test(_sig(), provider="template", created_ts=1.0)
    assert Proposal.model_validate_json(p.model_dump_json()).prompt_sha == p.prompt_sha


# ---- the gate: acceptance flows through the verdict layer ------------------

def test_generated_test_accepted_only_if_it_reproduces() -> None:
    proposal = propose_test(_sig(), provider="template", created_ts=1.0)
    # Target test fails WITH the original signature -> reproduces -> accepted.
    reproduces = (f'<testsuite name="s"><testcase classname="svc.Payment" name="test_charge">'
                  f'<error message="{_MSG}">{_STACK}</error></testcase></testsuite>')
    assert evaluate_proposal(proposal, reproduces, backend="junit").accepted

    # Target test passed -> not a reproduction -> rejected.
    passes = '<testsuite name="s"><testcase classname="svc.Payment" name="test_charge"/></testsuite>'
    assert not evaluate_proposal(proposal, passes, backend="junit").accepted


def test_reproduction_rejects_a_wrong_reason_failure() -> None:
    # #2: the target test fails, but with a DIFFERENT signature -> not genuine.
    proposal = propose_test(_sig(), provider="template", created_ts=1.0)
    wrong = ('<testsuite name="s"><testcase classname="svc.Payment" name="test_charge">'
             '<failure message="AssertionError: totally unrelated"/></testcase></testsuite>')
    ev = evaluate_proposal(proposal, wrong, backend="junit")
    assert not ev.accepted
    assert "different signature" in ev.reason


def test_heal_accepted_only_on_positive_evidence() -> None:
    proposal = propose_heal(_sig(), provider="template", created_ts=1.0)
    # Target test passing across TWO DISTINCT reruns (run_id r1, r2), signature
    # absent -> accepted. (JUnit has no run_id, so a heal needs tagged reruns.)
    healed = ("test_id,run_id,verdict\n"
              "svc.Payment::test_charge,r1,pass\n"
              "svc.Payment::test_charge,r2,pass\n")
    assert evaluate_proposal(proposal, healed, backend="jsonl").accepted


def test_heal_multitest_signature_needs_real_reruns(monkeypatch) -> None:
    # R3-2: a signature spanning >=2 tests must NOT be "healed" by a single run
    # just because it touches multiple tests — genuine reruns are required.
    monkeypatch.setenv("ASSAYLAB_SIGNING_KEY", "hex:" + "0123456789abcdef" * 4)
    sig = FailureSignature(signature_id="multi", template="boom", exception_type="E",
                           tests=["t::a", "t::b"], count=2, sample_message="boom")
    proposal = propose_heal(sig, provider="template", created_ts=1.0)
    # Two tests, ONE run (run_id r1), zero reruns -> must reject.
    one_run = ("test_id,run_id,verdict\nt::a,r1,pass\nt::b,r1,pass\n")
    assert not evaluate_proposal(proposal, one_run, backend="jsonl").accepted
    # Same two tests across TWO runs -> accepted.
    two_runs = ("test_id,run_id,verdict\nt::a,r1,pass\nt::b,r1,pass\nt::a,r2,pass\nt::b,r2,pass\n")
    assert evaluate_proposal(proposal, two_runs, backend="jsonl").accepted
    # Per-test coverage: t::a reran twice but t::b only once -> rejected (round-4 LOW).
    partial = ("test_id,run_id,verdict\nt::a,r1,pass\nt::a,r2,pass\nt::b,r1,pass\n")
    assert not evaluate_proposal(proposal, partial, backend="jsonl").accepted


def test_heal_rejects_duplicate_records_from_one_run() -> None:
    # MED: two rows for the SAME run must not count as two reruns.
    proposal = propose_heal(_sig(), provider="template", created_ts=1.0)
    dup = ("test_id,run_id,verdict\n"
           "svc.Payment::test_charge,r1,pass\n"
           "svc.Payment::test_charge,r1,pass\n")  # same run_id twice
    assert not evaluate_proposal(proposal, dup, backend="jsonl").accepted


def test_heal_rejects_empty_skipped_and_single_pass() -> None:
    # HIGH #1: an empty run, a skip, or a single lucky pass must NOT confirm a heal.
    proposal = propose_heal(_sig(), provider="template", created_ts=1.0)
    empty = "[]"
    assert not evaluate_proposal(proposal, empty, backend="jsonl").accepted
    skipped = ('<testsuite name="s"><testcase classname="svc.Payment" name="test_charge">'
               '<skipped/></testcase></testsuite>')
    assert not evaluate_proposal(proposal, skipped, backend="junit").accepted
    single = '<testsuite name="s"><testcase classname="svc.Payment" name="test_charge"/></testsuite>'
    assert not evaluate_proposal(proposal, single, backend="junit").accepted


def test_heal_rejects_if_target_still_fails() -> None:
    proposal = propose_heal(_sig(), provider="template", created_ts=1.0)
    still = (f'<testsuite name="s"><testcase classname="svc.Payment" name="test_charge">'
             f'<error message="{_MSG}">{_STACK}</error></testcase></testsuite>')
    assert not evaluate_proposal(proposal, still, backend="junit").accepted


def test_unknown_provider_rejected() -> None:
    import pytest

    from assaylab.errors import ConfigError

    with pytest.raises(ConfigError):
        resolve_provider("gpt-9000")
