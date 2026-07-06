"""Gate a proposal against a REAL run — acceptance flows through the verdict layer.

assaylab never runs the proposed code. Instead the user applies + runs it in
their own sandbox and feeds the resulting test output back here; the proposal is
accepted only if that graded run meets its acceptance criterion. This is what
keeps LLM output honest: a generated test counts only if it actually reproduces
the bug; a heal counts only if the flaky signature stops failing.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..config import Settings
from ..core import signature as _sig
from ..core.ingest import ingest
from .models import Proposal


@dataclass
class Evaluation:
    accepted: bool
    reason: str


def evaluate_proposal(
    proposal: Proposal,
    result_source: str,
    *,
    backend: str | None = None,
    settings: Settings | None = None,
) -> Evaluation:
    """Grade the returned run and decide whether the proposal is accepted."""
    settings = settings or Settings()
    records = ingest(result_source, backend=backend, settings=settings)
    check = proposal.acceptance.get("check")

    if check == "reproduces":
        target = str(proposal.acceptance.get("target_test", ""))
        matched = [r for r in records if r.test_id == target] if target else records
        if not matched:
            return Evaluation(False, f"target test {target!r} not found in the run")
        reproduced = any(r.outcome.failed for r in matched)
        return Evaluation(
            reproduced,
            f"generated test {'reproduced' if reproduced else 'did NOT reproduce'} the failure "
            f"({target})",
        )

    if check == "no_longer_fails":
        sig_id = str(proposal.acceptance.get("signature_id", ""))
        present = any(s.signature_id == sig_id for s in _sig.cluster(records))
        return Evaluation(
            not present,
            f"signature {sig_id} {'still fails' if present else 'no longer fails'} after the heal",
        )

    return Evaluation(False, f"unknown acceptance check {check!r}")
