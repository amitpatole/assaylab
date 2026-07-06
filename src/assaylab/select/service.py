"""Derive candidates from history, run selection, and attest the outcome."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .. import __version__
from ..attest import Receipt, hash_ids
from ..attest.keys import key_id, resolve_key
from ..config import Settings
from ..core.ingest import ingest
from ..errors import UnsafeSourceError
from ..rca.features import history_stats
from ..rca.risk import test_risk
from .engine import Candidate, Selection, select

_RECEIPT_MAX_BYTES = 4 * 1024 * 1024


def candidates_from_history(
    records: list, changed_files: set[str] | None = None
) -> list[Candidate]:
    """Build selection candidates: q = forecast failure prob, duration = mean seen."""
    stats = history_stats(records)
    # Mean duration + a representative file per test.
    durations: dict[str, list[float]] = {}
    files: dict[str, str] = {}
    for r in records:
        durations.setdefault(r.test_id, []).append(r.duration_s)
        if r.file and r.test_id not in files:
            files[r.test_id] = r.file

    changed = changed_files or set()
    out: list[Candidate] = []
    for test_id, st in stats.items():
        durs = [d for d in durations.get(test_id, []) if d > 0]
        dur = sum(durs) / len(durs) if durs else 1.0
        q = test_risk(st).forecast
        forced = files.get(test_id, "") in changed if changed else False
        out.append(Candidate(test_id=test_id, q=q, duration_s=dur, forced=forced))
    return sorted(out, key=lambda c: c.test_id)


def candidates_hash(candidates: list[Candidate]) -> str:
    """Stable hash committing to the candidate set AND its q/duration inputs."""
    payload = [
        {"t": c.test_id, "q": round(c.clamped_q, 6), "d": round(c.duration_s, 6), "f": c.forced}
        for c in sorted(candidates, key=lambda c: c.test_id)
    ]
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def attest(selection: Selection, candidates: list[Candidate], *, created_ts: float) -> Receipt:
    """Build and HMAC-sign a receipt binding the selection outcome."""
    key = resolve_key()
    receipt = Receipt(
        tool_version=__version__,
        created_ts=created_ts,
        objective=selection.objective,
        target_epsilon=selection.target_epsilon,
        time_budget_s=selection.time_budget_s,
        candidates_hash=candidates_hash(candidates),
        n_candidates=len(candidates),
        selected_hash=hash_ids(selection.selected),
        n_selected=len(selection.selected),
        skipped_hash=hash_ids(selection.skipped),
        n_skipped=len(selection.skipped),
        epsilon=selection.epsilon,
        confidence=selection.confidence,
        time_selected_s=selection.time_selected_s,
        time_all_s=selection.time_all_s,
        speedup=selection.speedup,
        key_id=key_id(key),
    )
    return receipt.sign(key)


def select_and_attest(
    source: str,
    *,
    target_epsilon: float | None = None,
    time_budget_s: float | None = None,
    changed_files: set[str] | None = None,
    created_ts: float,
    backend: str | None = None,
    settings: Settings | None = None,
) -> tuple[Selection, Receipt]:
    settings = settings or Settings()
    records = ingest(source, backend=backend, settings=settings)
    candidates = candidates_from_history(records, changed_files=changed_files)
    selection = select(candidates, target_epsilon=target_epsilon, time_budget_s=time_budget_s)
    receipt = attest(selection, candidates, created_ts=created_ts)
    return selection, receipt


def load_receipt(path: str) -> Receipt:
    p = Path(path)
    if not p.is_file():
        raise UnsafeSourceError(f"receipt not found: {path}")
    if p.stat().st_size > _RECEIPT_MAX_BYTES:
        raise UnsafeSourceError("receipt exceeds size cap")
    return Receipt.model_validate_json(p.read_text(encoding="utf-8"))


def verify_receipt(receipt: Receipt) -> bool:
    """Verify a receipt's signature against the resolved key (constant-time)."""
    return receipt.verify(resolve_key())


def verify_reproduction(receipt: Receipt, candidates: list[Candidate]) -> tuple[bool, str]:
    """Recompute the selection from the committed inputs and confirm it reproduces.

    Because selection is deterministic in ``(candidates, objective, target, budget)``
    — all of which the receipt commits to — a consumer holding the candidate set
    can re-run it and check the receipt's ``epsilon`` / selected-set are genuine,
    not merely signed. Returns ``(ok, reason)``. Does NOT check the HMAC (call
    :func:`verify_receipt` for that); this validates that the *bound is real*.
    """
    if candidates_hash(candidates) != receipt.candidates_hash:
        return False, "candidate set does not match the receipt's committed inputs"
    sel = select(candidates, target_epsilon=receipt.target_epsilon,
                 time_budget_s=receipt.time_budget_s)
    if hash_ids(sel.selected) != receipt.selected_hash:
        return False, "recomputed selection differs from the receipt"
    if abs(sel.epsilon - receipt.epsilon) > 1e-9:
        return False, f"recomputed epsilon {sel.epsilon} != receipt {receipt.epsilon}"
    return True, "reproduced: selection and confidence bound are genuine"
