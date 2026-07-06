"""The attested receipt: a signed commitment to a test-selection outcome.

The signature (HMAC-SHA256) covers the *result* — the inputs hash, the selected
and skipped sets (by hash + count), and the computed confidence bound ``epsilon``
— so it binds what actually happened, not merely that a run occurred. Verifying
is constant-time and, given the candidate inputs, re-derivable: a consumer can
recompute ``epsilon`` from the committed inputs and check it matches.
"""

from __future__ import annotations

import hashlib
import hmac
import json

from pydantic import BaseModel

SCHEMA = "assaylab.selection-receipt/1"


class Receipt(BaseModel):
    """A signed test-selection receipt. ``signature`` is not part of the signed body."""

    schema_id: str = SCHEMA
    tool_version: str = ""
    created_ts: float = 0.0

    objective: str = ""                     # "target_epsilon" | "time_budget"
    target_epsilon: float | None = None
    time_budget_s: float | None = None

    candidates_hash: str = ""               # sha256 of the canonical candidate set
    n_candidates: int = 0
    selected_hash: str = ""                 # sha256 of sorted selected test ids
    n_selected: int = 0
    skipped_hash: str = ""
    n_skipped: int = 0

    epsilon: float = 0.0                    # confidence lost: P(a skipped test would have failed)
    confidence: float = 1.0                 # 1 - epsilon
    time_selected_s: float = 0.0
    time_all_s: float = 0.0
    speedup: float = 1.0

    key_id: str = ""                        # which key signed this (non-secret)
    signature: str = ""                     # hex HMAC over the signed body

    # ---- signing ---------------------------------------------------------
    def signed_body(self) -> bytes:
        """Canonical bytes covered by the signature (everything but ``signature``)."""
        data = self.model_dump(exclude={"signature"})
        return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def sign(self, key: bytes) -> Receipt:
        self.signature = hmac.new(key, self.signed_body(), hashlib.sha256).hexdigest()
        return self

    def verify(self, key: bytes) -> bool:
        """Constant-time signature check."""
        expected = hmac.new(key, self.signed_body(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, self.signature)


def hash_ids(ids: list[str]) -> str:
    """Stable hash of a set of test ids (order-independent)."""
    joined = "\n".join(sorted(ids)).encode("utf-8")
    return hashlib.sha256(joined).hexdigest()
