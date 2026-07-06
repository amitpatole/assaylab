"""The `demo` pattern: broken -> FAIL, fixed -> PASS, no API key."""

from __future__ import annotations

from agentsensory import Verdict

from assaylab.adapters._demo_assets import broken_suite, fixed_suite
from assaylab.core import analyze


async def test_broken_suite_fails_with_two_signatures() -> None:
    r = await analyze(broken_suite(), backend="junit")
    assert r.verdict == Verdict.FAIL
    # 3 failures (1 assertion + 2 NPEs sharing a root) collapse to 2 signatures
    assert len(r.issues) == 2
    npe = next(i for i in r.issues if "NullPointer" in i.message)
    assert len(npe.detail["tests"]) == 2  # the two NPE tests clustered


async def test_fixed_suite_passes() -> None:
    r = await analyze(fixed_suite(), backend="junit")
    assert r.verdict == Verdict.PASS
