"""assaylab — validation intelligence for CI.

Failure-signature RCA, flaky-vs-real classification, and attested test-selection
with a verifiable confidence bound. Every result speaks the ``agentsensory``
contract (Report = verdict + grounded issues + Handoff).

The base wheel is light; heavy/optional surfaces (REST, MCP, dataset fetch) live
behind extras and are imported lazily.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

__version__ = "0.1.0"

if TYPE_CHECKING:  # names for type checkers only — no import cost at runtime
    from .config import Settings
    from .core import Assay, analyze, cluster, grade_records, ingest, perceive, to_handoff
    from .models import (
        FailureSignature,
        Issue,
        IssueKind,
        IssueSource,
        Outcome,
        Report,
        TestRecord,
    )

_LAZY: dict[str, tuple[str, str]] = {
    "analyze": ("assaylab.core", "analyze"),
    "grade_records": ("assaylab.core", "grade_records"),
    "ingest": ("assaylab.core", "ingest"),
    "perceive": ("assaylab.core", "perceive"),
    "to_handoff": ("assaylab.core", "to_handoff"),
    "cluster": ("assaylab.core", "cluster"),
    "Assay": ("assaylab.core", "Assay"),
    "Settings": ("assaylab.config", "Settings"),
    "Report": ("assaylab.models", "Report"),
    "Issue": ("assaylab.models", "Issue"),
    "IssueKind": ("assaylab.models", "IssueKind"),
    "IssueSource": ("assaylab.models", "IssueSource"),
    "Outcome": ("assaylab.models", "Outcome"),
    "TestRecord": ("assaylab.models", "TestRecord"),
    "FailureSignature": ("assaylab.models", "FailureSignature"),
}


def __getattr__(name: str) -> object:
    target = _LAZY.get(name)
    if target is None:
        raise AttributeError(f"module 'assaylab' has no attribute {name!r}")
    import importlib

    return getattr(importlib.import_module(target[0]), target[1])


__all__ = [
    "__version__",
    "Assay",
    "FailureSignature",
    "Issue",
    "IssueKind",
    "IssueSource",
    "Outcome",
    "Report",
    "Settings",
    "TestRecord",
    "analyze",
    "cluster",
    "grade_records",
    "ingest",
    "perceive",
    "to_handoff",
]
