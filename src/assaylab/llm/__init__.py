"""LLM-assisted test generation and self-healing — gated behind the verdict layer.

Every LLM output is a dry-run :class:`Proposal`; assaylab never executes or
applies it. Acceptance is decided by grading a real run against the proposal's
criterion (:func:`evaluate_proposal`).
"""

from __future__ import annotations

from .gate import Evaluation, evaluate_proposal
from .generate import propose_test
from .heal import propose_heal
from .models import Proposal, ProposalKind
from .provider import LLMProvider, resolve_provider

__all__ = [
    "Proposal",
    "ProposalKind",
    "LLMProvider",
    "resolve_provider",
    "propose_test",
    "propose_heal",
    "evaluate_proposal",
    "Evaluation",
]
