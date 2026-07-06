"""The Proposal: an LLM artifact assaylab never executes or applies."""

from __future__ import annotations

import hashlib
from enum import Enum

from pydantic import BaseModel, Field


class ProposalKind(str, Enum):
    TEST_GENERATION = "test_generation"
    SELF_HEAL = "self_heal"


class Proposal(BaseModel):
    """A dry-run suggestion + its provenance and acceptance criterion.

    ``applied`` is always False: assaylab produces the proposal and defines how
    to verify it, but a human/CI applies and runs it in their own sandbox. The
    verdict layer decides acceptance (see :mod:`assaylab.llm.gate`).
    """

    kind: ProposalKind
    target: str = Field(description="Signature id or test id the proposal addresses.")
    title: str = ""
    content: str = Field(description="Proposed test/patch text. NEVER executed by assaylab.")
    rationale: str = ""

    # Provenance — so a proposal is auditable and reproducible.
    provider: str = ""
    model: str = ""
    prompt_sha: str = ""
    created_ts: float = 0.0

    # Acceptance criterion, checked against a real run by the gate.
    acceptance: dict[str, object] = Field(default_factory=dict)

    applied: bool = False          # invariant: assaylab never applies a proposal
    status: str = "proposed"       # proposed | accepted | rejected


def prompt_sha(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8", "replace")).hexdigest()[:16]
