"""assaylab domain models, built on the agentsensory contract.

The test domain has no pixel (``BBox``) or time (``Span``) grounding, so each
issue grounds itself in ``detail`` (a JSON-safe dict) carrying the signature id,
affected tests, and file loci. ``Report`` / ``Issue`` subclass the agentsensory
base types so every result speaks the shared ``pass/warn/fail`` + ``Handoff``
language.
"""

from __future__ import annotations

from enum import Enum

from agentsensory import Confidence, IssueBase, ReportBase, Severity
from pydantic import BaseModel, Field


class Outcome(str, Enum):
    """Normalized outcome of a single test execution."""

    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"
    SKIP = "skip"

    @property
    def failed(self) -> bool:
        return self in (Outcome.FAIL, Outcome.ERROR)


class IssueKind(str, Enum):
    """assaylab issue kinds (the domain vocabulary carried in ``Issue.kind``)."""

    FAILURE_SIGNATURE = "failure_signature"  # a cluster of failures sharing a fingerprint
    NEW_FAILURE = "new_failure"              # a signature not seen in the baseline
    FLAKY_SUSPECT = "flaky_suspect"          # same test+commit both passed and failed (P2)
    OTHER = "other"


class IssueSource(str, Enum):
    """Which analysis produced an issue."""

    SIGNATURE_CLUSTER = "signature_cluster"
    INGEST = "ingest"


class TestRecord(BaseModel):
    """One test execution, normalized across ingestion formats.

    This is the universal internal schema every backend maps onto:
    ``(project, commit, test_id, run_id, outcome, duration, message, stacktrace)``.
    """

    __test__ = False  # not a pytest test class despite the ``Test`` prefix

    test_id: str = Field(description="Fully-qualified test identifier (suite::name).")
    outcome: Outcome
    project: str = ""
    commit: str = ""
    run_id: str = ""
    duration_s: float = 0.0
    file: str | None = None
    line: int | None = None
    message: str = ""
    stacktrace: str = ""


class FailureSignature(BaseModel):
    """A cluster of failing executions that share a normalized fingerprint.

    The fingerprint is a stable hash of the templated (variable-stripped)
    error type + message + top stack frames — so runs that differ only in
    addresses, line numbers, temp paths or timestamps collapse together.
    """

    signature_id: str = Field(description="Stable short hash of the normalized template.")
    template: str = Field(description="The normalized, variable-stripped failure text.")
    exception_type: str = ""
    count: int = 0
    tests: list[str] = Field(default_factory=list, description="Distinct test_ids in this cluster.")
    files: list[str] = Field(default_factory=list, description="Distinct source files touched.")
    sample_message: str = Field(default="", description="One representative raw message.")

    def to_detail(self) -> dict[str, object]:
        """JSON-safe grounding payload for an ``Issue.detail``."""
        return {
            "signature_id": self.signature_id,
            "exception_type": self.exception_type,
            "count": self.count,
            "tests": self.tests[:50],
            "files": self.files[:50],
            "template": self.template[:2000],
        }


class Issue(IssueBase):
    """assaylab issue — an ``agentsensory.IssueBase`` with test-domain grounding in ``detail``."""

    @classmethod
    def from_signature(
        cls,
        sig: FailureSignature,
        *,
        kind: IssueKind = IssueKind.FAILURE_SIGNATURE,
        severity: Severity = Severity.ERROR,
        confidence: Confidence = Confidence.HIGH,
    ) -> Issue:
        ntests = len(sig.tests)
        msg = (
            f"{sig.exception_type or 'Failure'} across {ntests} "
            f"test{'s' if ntests != 1 else ''} ({sig.count} run{'s' if sig.count != 1 else ''}): "
            f"{sig.sample_message[:200]}"
        )
        issue = IssueBase.make(
            kind.value,
            severity,
            msg,
            confidence=confidence,
            source=IssueSource.SIGNATURE_CLUSTER.value,
            detail=sig.to_detail(),
        )
        return cls(**issue.model_dump())


class Report(ReportBase):
    """assaylab report — an ``agentsensory.ReportBase`` (verdict + issues + handoff)."""
