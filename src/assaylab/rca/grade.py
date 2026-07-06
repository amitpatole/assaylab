"""RCA-aware grading: cluster -> root-cause + flaky + risk -> graded Report.

Extends P1's grading with root-cause categorization, flaky-vs-real
classification, and per-signature risk. The verdict rule becomes:

* no failures                          -> PASS
* at least one *real* failure          -> FAIL
* failures present but **all flaky**   -> WARN  (don't block the gate on flakiness)

Each issue's ``detail`` carries the grounding: root cause + confidence +
evidence, the flaky verdict, and the max per-test risk.
"""

from __future__ import annotations

import time

from agentsensory import Confidence, IssueBase, Severity, Verdict

from ..core import signature as _sig
from ..models import FailureSignature, Issue, IssueKind, Report, TestRecord
from .features import history_stats
from .flaky import flaky_probability
from .risk import test_risk
from .rootcause import categorize


def _sig_risk(sig: FailureSignature, stats) -> float:  # type: ignore[no-untyped-def]
    risks = [test_risk(stats[t]).score for t in sig.tests if t in stats]
    return max(risks) if risks else 0.0


def grade_with_rca(
    records: list[TestRecord],
    *,
    baseline_ids: set[str] | None = None,
    model: object | None = None,
    backend: str = "unknown",
) -> Report:
    start = time.perf_counter()
    signatures = _sig.cluster(records)
    stats = history_stats(records)
    n_total = len(records)
    n_fail = len(_sig.failing(records))
    n_pass = len(_sig.passing(records))

    issues: list[IssueBase] = []
    n_flaky = n_real = n_new = 0

    for s in signatures:
        cat = categorize(s)
        from .features import signature_features

        feats = signature_features(s.tests, stats)
        flaky = flaky_probability(feats, s.tests, stats, model=model)
        risk = _sig_risk(s, stats)
        is_new = baseline_ids is not None and s.signature_id not in baseline_ids

        if flaky.is_flaky:
            n_flaky += 1
            kind = IssueKind.FLAKY_SUSPECT
            severity = Severity.WARNING
            conf = Confidence.MEDIUM
        else:
            n_real += 1
            kind = IssueKind.NEW_FAILURE if is_new else IssueKind.FAILURE_SIGNATURE
            severity = Severity.CRITICAL if is_new else Severity.ERROR
            conf = Confidence.HIGH
        if is_new:
            n_new += 1

        issues.append(Issue.from_signature(
            s, kind=kind, severity=severity, confidence=conf,
            extra={
                "root_cause": cat.cause.value,
                "root_cause_confidence": cat.confidence,
                "root_cause_evidence": cat.evidence,
                "flaky": flaky.is_flaky,
                "flaky_probability": flaky.probability,
                "flaky_evidence": flaky.evidence,
                "risk": round(risk, 4),
                "new": is_new,
            },
        ))

    if not signatures:
        verdict = Verdict.PASS
        summary = f"{n_pass}/{n_total} tests passed — no failure signatures."
    elif n_real == 0:
        verdict = Verdict.WARN
        summary = (f"{n_flaky} flaky-suspect signature(s) only, no real failures; "
                   f"{n_pass}/{n_total} passed. Not blocking.")
    else:
        verdict = Verdict.FAIL
        parts = [f"{n_real} real"]
        if n_flaky:
            parts.append(f"{n_flaky} flaky")
        if baseline_ids is not None:
            parts.append(f"{n_new} new")
        summary = (f"{n_fail} failing execution(s) across {len(signatures)} signature(s) "
                   f"({', '.join(parts)}); {n_pass}/{n_total} passed.")

    elapsed_ms = int((time.perf_counter() - start) * 1000)
    return Report(verdict=verdict, summary=summary, issues=issues,
                  backend=backend, elapsed_ms=elapsed_ms)
