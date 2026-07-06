"""LLM-assisted test-gen / self-heal — proposals, gating, provenance."""

from __future__ import annotations

from assaylab.llm import (
    Proposal,
    ProposalKind,
    evaluate_proposal,
    propose_heal,
    propose_test,
    resolve_provider,
)
from assaylab.models import FailureSignature


def _sig() -> FailureSignature:
    return FailureSignature(
        signature_id="abc123",
        template="NullPointerException || card was null",
        exception_type="NullPointerException",
        tests=["svc.Payment::test_charge"],
        count=3,
        sample_message="NullPointerException: card was null",
    )


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
    # Run where the target test FAILED -> reproduces -> accepted.
    reproduces = ('<testsuite name="s"><testcase classname="svc.Payment" name="test_charge">'
                  '<failure message="NullPointerException"/></testcase></testsuite>')
    ev = evaluate_proposal(proposal, reproduces, backend="junit")
    assert ev.accepted

    # Run where it passed -> does NOT reproduce -> rejected.
    passes = ('<testsuite name="s"><testcase classname="svc.Payment" name="test_charge"/>'
              '</testsuite>')
    ev2 = evaluate_proposal(proposal, passes, backend="junit")
    assert not ev2.accepted


def test_heal_accepted_only_if_signature_stops_failing() -> None:
    proposal = propose_heal(_sig(), provider="template", created_ts=1.0)
    # After the heal, a run with no failures -> signature absent -> accepted.
    clean = '<testsuite name="s"><testcase classname="svc.Payment" name="test_charge"/></testsuite>'
    ev = evaluate_proposal(proposal, clean, backend="junit")
    assert ev.accepted


def test_unknown_provider_rejected() -> None:
    import pytest

    from assaylab.errors import ConfigError

    with pytest.raises(ConfigError):
        resolve_provider("gpt-9000")
