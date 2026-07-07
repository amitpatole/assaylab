"""The Proposal: an LLM artifact assaylab never executes or applies."""

from __future__ import annotations

import hashlib
import hmac
import json
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

    # HMAC over the trust-relevant fields, set at generation. The gate refuses to
    # grade a proposal whose signature doesn't verify — so a hand-crafted JSON
    # can't weaken its own acceptance criteria (they're bound to the tool that
    # derived them from a real signature).
    key_id: str = ""
    signature: str = ""

    def signed_body(self) -> bytes:
        """Canonical bytes covered by the signature (everything but the signature)."""
        data = self.model_dump(exclude={"signature"})
        return json.dumps(data, sort_keys=True, separators=(",", ":"),
                          allow_nan=False).encode("utf-8")

    def sign(self, key: bytes) -> Proposal:
        self.signature = hmac.new(key, self.signed_body(), hashlib.sha256).hexdigest()
        return self

    def verify(self, key: bytes) -> bool:
        if not self.signature:
            return False
        expected = hmac.new(key, self.signed_body(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, self.signature)


def prompt_sha(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8", "replace")).hexdigest()[:16]
