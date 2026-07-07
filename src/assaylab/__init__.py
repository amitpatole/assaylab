"""assaylab — validation intelligence for CI.

Failure-signature RCA, flaky-vs-real classification, and attested test-selection
with a verifiable confidence bound. Every result speaks the ``agentsensory``
contract (Report = verdict + grounded issues + Handoff).

The base wheel is light; heavy/optional surfaces (REST, MCP, dataset fetch) live
behind extras and are imported lazily.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

__version__ = "0.3.0"

if TYPE_CHECKING:  # names for type checkers only — no import cost at runtime
    from .attest import Receipt, resolve_key
    from .config import Settings
    from .core import Assay, analyze, cluster, grade_records, ingest, perceive, to_handoff
    from .dashboard import build_report
    from .llm import Proposal, evaluate_proposal, propose_heal, propose_test, resolve_provider
    from .models import (
        FailureSignature,
        Issue,
        IssueKind,
        IssueSource,
        Outcome,
        Report,
        TestRecord,
    )
    from .rca import (
        LogisticModel,
        RootCause,
        categorize,
        grade_with_rca,
        history_stats,
        rank_risk,
        train,
    )
    from .select import Candidate, Selection, select, select_and_attest, verify_receipt

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
    "grade_with_rca": ("assaylab.rca", "grade_with_rca"),
    "categorize": ("assaylab.rca", "categorize"),
    "RootCause": ("assaylab.rca", "RootCause"),
    "rank_risk": ("assaylab.rca", "rank_risk"),
    "history_stats": ("assaylab.rca", "history_stats"),
    "train": ("assaylab.rca", "train"),
    "LogisticModel": ("assaylab.rca", "LogisticModel"),
    "Candidate": ("assaylab.select", "Candidate"),
    "Selection": ("assaylab.select", "Selection"),
    "select": ("assaylab.select", "select"),
    "select_and_attest": ("assaylab.select", "select_and_attest"),
    "verify_receipt": ("assaylab.select", "verify_receipt"),
    "Receipt": ("assaylab.attest", "Receipt"),
    "resolve_key": ("assaylab.attest", "resolve_key"),
    "build_report": ("assaylab.dashboard", "build_report"),
    "propose_test": ("assaylab.llm", "propose_test"),
    "propose_heal": ("assaylab.llm", "propose_heal"),
    "evaluate_proposal": ("assaylab.llm", "evaluate_proposal"),
    "resolve_provider": ("assaylab.llm", "resolve_provider"),
    "Proposal": ("assaylab.llm", "Proposal"),
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
    "Candidate",
    "FailureSignature",
    "Issue",
    "IssueKind",
    "IssueSource",
    "LogisticModel",
    "Outcome",
    "Proposal",
    "Receipt",
    "Report",
    "RootCause",
    "Selection",
    "Settings",
    "TestRecord",
    "analyze",
    "build_report",
    "categorize",
    "cluster",
    "evaluate_proposal",
    "grade_records",
    "grade_with_rca",
    "history_stats",
    "ingest",
    "perceive",
    "propose_heal",
    "propose_test",
    "rank_risk",
    "resolve_key",
    "resolve_provider",
    "select",
    "select_and_attest",
    "to_handoff",
    "train",
    "verify_receipt",
]
