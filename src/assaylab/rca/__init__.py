"""Root-cause analysis: categorization, flaky-vs-real, risk, and a learned model.

Everything here is history-aware and interpretable; the learned model
(:class:`LogisticModel`) is optional and JSON-persisted (never pickle).
"""

from __future__ import annotations

from .features import TestStats, history_stats, signature_features
from .flaky import FlakyVerdict, flaky_heuristic, flaky_probability
from .grade import grade_with_rca
from .model import LogisticModel, train
from .risk import Risk, rank_risk, test_risk
from .rootcause import Categorization, RootCause, categorize

__all__ = [
    "TestStats",
    "history_stats",
    "signature_features",
    "FlakyVerdict",
    "flaky_heuristic",
    "flaky_probability",
    "grade_with_rca",
    "LogisticModel",
    "train",
    "Risk",
    "rank_risk",
    "test_risk",
    "Categorization",
    "RootCause",
    "categorize",
]
