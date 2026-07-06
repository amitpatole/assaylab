"""Grade test records into an agentsensory :class:`Report`.

P1 verdict rule (deterministic):

* no failing records            -> PASS
* failing records present       -> FAIL, one issue per failure signature
* a signature absent from a supplied baseline is marked ``NEW_FAILURE`` (higher
  risk) rather than a plain ``FAILURE_SIGNATURE``.

Flaky-vs-real downgrading to WARN arrives in P2; the hook (baseline diff) is
already here.
"""

from __future__ import annotations

import time

from agentsensory import IssueBase, Severity, Verdict

from ..config import Settings
from ..models import Issue, IssueKind, Report, TestRecord
from . import signature as sig
from .ingest import ingest


def grade_records(
    records: list[TestRecord],
    *,
    baseline_ids: set[str] | None = None,
    backend: str = "unknown",
) -> Report:
    """Cluster failures and return a graded :class:`Report`."""
    start = time.perf_counter()
    signatures = sig.cluster(records)
    n_total = len(records)
    n_fail = len(sig.failing(records))
    n_pass = len(sig.passing(records))

    issues: list[IssueBase] = []
    n_new = 0
    for s in signatures:
        is_new = baseline_ids is not None and s.signature_id not in baseline_ids
        if is_new:
            n_new += 1
        issues.append(
            Issue.from_signature(
                s,
                kind=IssueKind.NEW_FAILURE if is_new else IssueKind.FAILURE_SIGNATURE,
                severity=Severity.CRITICAL if is_new else Severity.ERROR,
            )
        )

    if not signatures:
        verdict = Verdict.PASS
        summary = f"{n_pass}/{n_total} tests passed — no failure signatures."
    else:
        verdict = Verdict.FAIL
        newpart = f", {n_new} new" if baseline_ids is not None else ""
        summary = (
            f"{n_fail} failing execution(s) across {len(signatures)} "
            f"signature(s){newpart}; {n_pass}/{n_total} passed."
        )

    elapsed_ms = int((time.perf_counter() - start) * 1000)
    return Report(
        verdict=verdict,
        summary=summary,
        issues=issues,
        backend=backend,
        elapsed_ms=elapsed_ms,
    )


async def analyze(
    source: str,
    *,
    backend: str | None = None,
    baseline: str | None = None,
    settings: Settings | None = None,
) -> Report:
    """Ingest ``source`` (and optional ``baseline``) and grade it."""
    settings = settings or Settings()
    records = ingest(source, backend=backend, settings=settings)
    baseline_ids: set[str] | None = None
    if baseline is not None:
        base_records = ingest(baseline, backend=backend, settings=settings)
        baseline_ids = {s.signature_id for s in sig.cluster(base_records)}
    return grade_records(records, baseline_ids=baseline_ids, backend=backend or "inferred")
