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
        # A generated test counts only if the named target test FAILS *with the
        # original signature* — not merely any red result (closes wrong-reason
        # acceptance and the empty-target all-records fallback: fail closed).
        target = str(proposal.acceptance.get("target_test", ""))
        target_sig = proposal.target
        if not target:
            return Evaluation(False, "proposal names no target test — cannot verify reproduction")
        failing = [r for r in records if r.test_id == target and r.outcome.failed]
        if not any(r.test_id == target for r in records):
            return Evaluation(False, f"target test {target!r} not found in the run")
        if not failing:
            return Evaluation(False, f"target test {target!r} did not fail — no reproduction")
        seen_sigs = {_sig.fingerprint(r)[0] for r in failing}
        if target_sig in seen_sigs:
            return Evaluation(True, f"reproduced signature {target_sig} on {target}")
        return Evaluation(
            False,
            f"{target} failed but with a different signature ({', '.join(sorted(seen_sigs))}) "
            f"than the target {target_sig} — not a genuine reproduction",
        )

    if check == "no_longer_fails":
        # A heal counts only on POSITIVE evidence: the target tests are present,
        # none fail, the signature is gone, and there are enough passing runs to
        # rule out a single lucky pass / skip / empty run (closes HIGH #1).
        from ..models import Outcome

        sig_id = str(proposal.acceptance.get("signature_id", ""))
        raw_targets = proposal.acceptance.get("target_tests", [])
        target_tests = {str(t) for t in raw_targets} if isinstance(raw_targets, (list, tuple, set)) else set()
        raw_min = proposal.acceptance.get("min_pass_runs", 2)
        min_pass = int(raw_min) if isinstance(raw_min, (int, float, str)) else 2

        if target_tests:
            present = {r.test_id for r in records}
            missing = sorted(target_tests - present)
            if missing:
                return Evaluation(False, f"target test(s) absent from the run: {missing}")
            target_recs = [r for r in records if r.test_id in target_tests]
        else:
            target_recs = records

        if any(r.outcome.failed for r in target_recs):
            return Evaluation(False, "a target test still failed after the heal")
        passes = sum(1 for r in target_recs if r.outcome == Outcome.PASS)
        if passes < min_pass:
            return Evaluation(
                False,
                f"insufficient passing evidence ({passes} < {min_pass}) — a skip, single lucky "
                f"pass, or empty run does not confirm a heal",
            )
        if any(s.signature_id == sig_id for s in _sig.cluster(records)):
            return Evaluation(False, f"signature {sig_id} still present after the heal")
        return Evaluation(
            True, f"signature {sig_id} no longer fails; {passes} passing run(s) of target test(s)"
        )

    return Evaluation(False, f"unknown acceptance check {check!r}")
