"""Ingest a source into normalized test records."""

from __future__ import annotations

from ..backends import infer_backend, resolve_backend
from ..config import Settings
from ..models import TestRecord


def ingest(
    source: str,
    *,
    backend: str | None = None,
    settings: Settings | None = None,
) -> list[TestRecord]:
    """Read ``source`` into :class:`TestRecord`s using ``backend`` (inferred if None)."""
    settings = settings or Settings()
    name = backend or infer_backend(source)
    be = resolve_backend(name, settings=settings)
    return be.parse(source, settings=settings)
