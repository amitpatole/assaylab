"""Attested test-selection with a verifiable confidence bound."""

from __future__ import annotations

from .engine import Candidate, Selection, select
from .service import (
    attest,
    candidates_from_history,
    candidates_hash,
    load_receipt,
    select_and_attest,
    verify_receipt,
)

__all__ = [
    "Candidate",
    "Selection",
    "select",
    "attest",
    "candidates_from_history",
    "candidates_hash",
    "load_receipt",
    "select_and_attest",
    "verify_receipt",
]
