"""assaylab core sense: ingest -> cluster -> grade -> handoff."""

from __future__ import annotations

from .analyze import analyze, grade_records
from .ingest import ingest
from .perceive import perceive, to_handoff
from .sense import Assay
from .signature import cluster, fingerprint, normalize

__all__ = [
    "Assay",
    "analyze",
    "grade_records",
    "ingest",
    "perceive",
    "to_handoff",
    "cluster",
    "fingerprint",
    "normalize",
]
