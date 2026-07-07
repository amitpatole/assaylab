"""Propose a regression test from a failure signature (dry-run)."""

from __future__ import annotations

from ..attest.keys import key_id, resolve_key
from ..models import FailureSignature
from .models import Proposal, ProposalKind, prompt_sha
from .provider import LLMProvider, resolve_provider

_SYSTEM = (
    "You are a careful software test engineer. Given a failure signature, write a single, "
    "minimal regression test that reproduces the failure and asserts the corrected behavior. "
    "Return only the test code. Do not execute anything."
)


def _build_prompt(sig: FailureSignature) -> str:
    tests = ", ".join(sig.tests[:5]) or "(unknown)"
    return (
        "Generate a test — a regression test that reproduces this failure:\n\n"
        f"exception: {sig.exception_type or '(none)'}\n"
        f"message: {sig.sample_message[:500]}\n"
        f"affected tests: {tests}\n"
        f"normalized template: {sig.template[:800]}\n\n"
        "The test should FAIL on the current (buggy) code and PASS once fixed."
    )


def propose_test(
    sig: FailureSignature,
    *,
    provider: LLMProvider | str | None = None,
    created_ts: float,
) -> Proposal:
    prov = provider if isinstance(provider, LLMProvider) else resolve_provider(provider)
    prompt = _build_prompt(sig)
    content = prov.complete(prompt, system=_SYSTEM)
    target_test = sig.tests[0] if sig.tests else sig.signature_id
    proposal = Proposal(
        kind=ProposalKind.TEST_GENERATION,
        target=sig.signature_id,
        title=f"regression test for {sig.exception_type or 'failure'} ({sig.signature_id})",
        content=content,
        rationale=(f"Reproduces the '{sig.exception_type or 'failure'}' signature "
                   f"affecting {len(sig.tests)} test(s)."),
        provider=prov.name,
        model=getattr(prov, "model", ""),
        prompt_sha=prompt_sha(prompt),
        created_ts=created_ts,
        acceptance={
            "check": "reproduces",
            "target_test": target_test,
            "expected_current_outcome": "fail",
        },
    )
    key = resolve_key()
    proposal.key_id = key_id(key)
    return proposal.sign(key)
