"""Deterministic, key-free provider.

Emits a pytest regression-test skeleton (or a heal note) from the prompt's
structured hints. Not a real LLM — a reproducible fallback so the whole
LLM-assisted flow works with no API key, in CI, and in tests. Real providers
(claude/ollama) produce richer output; the *shape* of the proposal is identical.
"""

from __future__ import annotations

from ..provider import _cap


class TemplateProvider:
    name = "template"

    def available(self) -> bool:
        return True

    def complete(self, prompt: str, *, system: str = "", max_tokens: int = 4096) -> str:
        # The prompt carries a fenced payload we echo into a deterministic stub.
        # We do NOT interpret it as code — assaylab never executes generated code.
        marker = "regression test that reproduces this failure"
        if marker in prompt or "generate a test" in prompt.lower():
            return _cap(_TEST_SKELETON)
        return _cap(_HEAL_NOTE)


_TEST_SKELETON = '''\
# Proposed regression test (DRY-RUN — review and run in your own sandbox).
# assaylab did not execute this. It should FAIL on the current code and PASS
# once the root cause is fixed.
import pytest


def test_regression_for_signature():
    """Reproduce the clustered failure, then assert the fixed behavior."""
    # Arrange: construct the input that triggered the failure signature.
    # Act:     call the code path named in the failure's stack frames.
    # Assert:  the corrected expectation (this line should fail pre-fix).
    pytest.skip("fill in arrange/act/assert from the signature, then remove skip")
'''

_HEAL_NOTE = '''\
# Proposed mitigation (DRY-RUN — review before applying; assaylab will not apply it).
# The signature looks flaky (same commit both passed and failed). Options,
# least-invasive first:
#   1. Fix the nondeterminism (preferred): pin the clock/seed/order the test depends on.
#   2. Add a bounded retry to the flaky assertion (masks, does not fix).
#   3. Quarantine the test (mark xfail/skip) and file a tracking issue.
# Acceptance: after the change, the signature must not FAIL across N reruns.
'''
