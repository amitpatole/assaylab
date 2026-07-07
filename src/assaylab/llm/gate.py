"""Gate a proposal against a REAL run — acceptance flows through the verdict layer.

assaylab never runs the proposed code. Instead the user applies + runs it in
their own sandbox and feeds the resulting test output back here; the proposal is
accepted only if that graded run meets its acceptance criterion. This is what
keeps LLM output honest: a generated test counts only if it actually reproduces
the bug; a heal counts only if the flaky signature stops failing.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..attest.keys import resolve_key
from ..config import Settings
from ..core import signature as _sig
from ..core.ingest import ingest
from .models import Proposal

# Hardcoded floor on passing evidence for a heal — never trusted from the proposal.
_MIN_PASS_FLOOR = 2


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
    """Grade the returned run and decide whether the proposal is accepted.

    The proposal is treated as UNTRUSTED: its signature must verify (it was
    signed at generation by the tool that derived the criteria from a real
    signature), or we refuse to grade it. This stops a hand-crafted proposal
    JSON from weakening its own acceptance criteria.
    """
    settings = settings or Settings()
    if not proposal.verify(resolve_key()):
        return Evaluation(
            False,
            "proposal signature is missing or invalid — refusing to grade an untrusted proposal "
            "(only an assaylab-generated proposal signed with this install's key can be verified)",
        )
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
        raw_min = proposal.acceptance.get("min_pass_runs", _MIN_PASS_FLOOR)
        req_min = int(raw_min) if isinstance(raw_min, (int, float, str)) else _MIN_PASS_FLOOR
        # Never trust a below-floor threshold from the proposal (defence in depth
        # even though the signature already binds it).
        min_pass = max(_MIN_PASS_FLOOR, req_min)

        # A heal MUST name its target tests; an empty set can't be positively verified.
        if not target_tests:
            return Evaluation(False, "heal names no target tests — cannot confirm a fix")
        present = {r.test_id for r in records}
        missing = sorted(target_tests - present)
        if missing:
            return Evaluation(False, f"target test(s) absent from the run: {missing}")
        target_recs = [r for r in records if r.test_id in target_tests]

        if any(r.outcome.failed for r in target_recs):
            return Evaluation(False, "a target test still failed after the heal")
        # EACH target test must pass in >= min_pass DISTINCT reruns. A rerun is
        # keyed by run_id (commit fallback); both absent -> one run collapses to a
        # single key and can't clear the floor. Requiring per-test coverage (not
        # a union across tests) means a multi-test signature can't be "healed" by
        # one run, and every affected test must actually be re-run.
        per_test_runs: dict[str, set[str]] = {}
        for r in target_recs:
            if r.outcome == Outcome.PASS:
                per_test_runs.setdefault(r.test_id, set()).add(r.run_id or r.commit)
        insufficient = sorted(t for t in target_tests
                              if len(per_test_runs.get(t, set())) < min_pass)
        if insufficient:
            return Evaluation(
                False,
                f"target test(s) {insufficient} lack {min_pass} distinct passing reruns — a single "
                f"run, skip, empty run, or duplicated record does not confirm a heal",
            )
        passes = min(len(per_test_runs[t]) for t in target_tests)
        if any(s.signature_id == sig_id for s in _sig.cluster(records)):
            return Evaluation(False, f"signature {sig_id} still present after the heal")
        return Evaluation(
            True, f"signature {sig_id} no longer fails; {passes} distinct passing rerun(s)"
        )

    return Evaluation(False, f"unknown acceptance check {check!r}")
