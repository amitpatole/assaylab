"""Propose a mitigation for a flaky signature (dry-run — never auto-applied)."""

from __future__ import annotations

from ..models import FailureSignature
from .models import Proposal, ProposalKind, prompt_sha
from .provider import LLMProvider, resolve_provider

_SYSTEM = (
    "You are a careful software test engineer. Given a flaky test signature, propose the "
    "least-invasive mitigation (fix the nondeterminism if possible; retry or quarantine only "
    "as a fallback). Explain the trade-off. Do not apply or execute anything."
)


def _build_prompt(sig: FailureSignature) -> str:
    tests = ", ".join(sig.tests[:5]) or "(unknown)"
    return (
        "Propose a self-heal for this flaky failure signature:\n\n"
        f"exception: {sig.exception_type or '(none)'}\n"
        f"message: {sig.sample_message[:500]}\n"
        f"affected tests: {tests}\n\n"
        "The signature flips between pass and fail. Suggest a mitigation and its trade-off."
    )


def propose_heal(
    sig: FailureSignature,
    *,
    provider: LLMProvider | str | None = None,
    created_ts: float,
) -> Proposal:
    prov = provider if isinstance(provider, LLMProvider) else resolve_provider(provider)
    prompt = _build_prompt(sig)
    content = prov.complete(prompt, system=_SYSTEM)
    return Proposal(
        kind=ProposalKind.SELF_HEAL,
        target=sig.signature_id,
        title=f"heal flaky {sig.signature_id}",
        content=content,
        rationale=f"Signature {sig.signature_id} is flaky across {len(sig.tests)} test(s).",
        provider=prov.name,
        model=getattr(prov, "model", ""),
        prompt_sha=prompt_sha(prompt),
        created_ts=created_ts,
        acceptance={
            "check": "no_longer_fails",
            "signature_id": sig.signature_id,
            "expected_after": "not_fail",
        },
    )
