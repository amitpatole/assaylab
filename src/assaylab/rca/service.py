"""High-level RCA entry points used by the CLI/adapters."""

from __future__ import annotations

from pathlib import Path

from ..config import Settings
from ..core import signature as _sig
from ..core.ingest import ingest
from ..errors import UnsafeSourceError
from ..models import Report
from .features import history_stats
from .grade import grade_with_rca
from .model import LogisticModel

# A model file is small; cap the read so a huge "model" can't exhaust memory.
_MODEL_MAX_BYTES = 4 * 1024 * 1024


def load_model(path: str) -> LogisticModel:
    """Load a JSON logistic model (never pickle — inert load, no code execution)."""
    p = Path(path)
    if not p.is_file():
        raise UnsafeSourceError(f"model file not found: {path}")
    if p.stat().st_size > _MODEL_MAX_BYTES:
        raise UnsafeSourceError("model file exceeds size cap")
    return LogisticModel.from_json(p.read_text(encoding="utf-8"))


async def analyze(
    source: str,
    *,
    backend: str | None = None,
    baseline: str | None = None,
    model_path: str | None = None,
    settings: Settings | None = None,
) -> Report:
    """Ingest and grade with full RCA (root cause + flaky + risk)."""
    settings = settings or Settings()
    records = ingest(source, backend=backend, settings=settings)
    baseline_ids: set[str] | None = None
    if baseline is not None:
        base = ingest(baseline, backend=backend, settings=settings)
        baseline_ids = {s.signature_id for s in _sig.cluster(base)}
    model = load_model(model_path) if model_path else None
    return grade_with_rca(records, baseline_ids=baseline_ids, model=model,
                          backend=backend or "inferred")


def stats_for(source: str, *, backend: str | None = None, settings: Settings | None = None):  # type: ignore[no-untyped-def]
    """Per-test history stats for a source (used by ``risk``/``flaky`` commands)."""
    settings = settings or Settings()
    return history_stats(ingest(source, backend=backend, settings=settings))
