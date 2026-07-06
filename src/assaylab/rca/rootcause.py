"""Root-cause categorization.

A transparent, always-available baseline: map a failure signature to a
root-cause category with a confidence and the evidence that fired. This is the
interpretable floor the learned model (``model.py``) is measured against, and
what grounds every RCA verdict so a human can audit *why* a cause was assigned.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from ..models import FailureSignature


class RootCause(str, Enum):
    ASSERTION = "assertion"          # a genuine assertion / expectation mismatch
    NULL_DEREF = "null_deref"        # null/None dereference
    TIMEOUT = "timeout"              # timed out / deadline exceeded
    DEPENDENCY = "dependency"        # import/module/class-not-found, version conflict
    CONFIG = "config"                # missing env var / property / bad config
    RESOURCE = "resource"            # OOM, disk, file-not-found, connection pool
    CONCURRENCY = "concurrency"      # race, deadlock, non-deterministic ordering
    NETWORK = "network"              # connection refused/reset, DNS, socket
    ENVIRONMENT = "environment"      # CI/env-specific (paths, permissions, clock)
    UNKNOWN = "unknown"


@dataclass
class Categorization:
    cause: RootCause
    confidence: float  # 0..1
    evidence: str


# Ordered rules: (cause, compiled pattern, weight). Higher cumulative weight wins.
_RULES: list[tuple[RootCause, re.Pattern[str], float]] = [
    (RootCause.NULL_DEREF, re.compile(r"null\s*pointer|nullpointerexception|nonetype|"
                                      r"attributeerror.*nonetype|null reference", re.I), 1.0),
    (RootCause.TIMEOUT, re.compile(r"timeout|timed out|deadline exceeded|"
                                   r"exceeded.*(seconds|ms)\b", re.I), 1.0),
    (RootCause.DEPENDENCY, re.compile(r"modulenotfound|importerror|no module named|"
                                      r"classnotfound|noclassdeffound|no such method|"
                                      r"unsatisfied.*dependency", re.I), 1.0),
    (RootCause.NETWORK, re.compile(r"connection refused|connection reset|econnrefused|"
                                   r"socket|dns|unknownhost|no route to host|"
                                   r"connectexception", re.I), 0.9),
    (RootCause.RESOURCE, re.compile(r"outofmemory|oom|filenotfound|no such file|"
                                    r"disk|too many open files|no space left|"
                                    r"connection pool", re.I), 0.9),
    (RootCause.CONFIG, re.compile(r"missing.*(env|environment|property|config)|"
                                  r"not set|keyerror|missing required|"
                                  r"illegalargument.*config", re.I), 0.7),
    (RootCause.CONCURRENCY, re.compile(r"deadlock|race condition|concurrentmodification|"
                                       r"interrupted|lock|thread", re.I), 0.7),
    (RootCause.ASSERTION, re.compile(r"assert|assertionerror|expected.*(but|got)|"
                                     r"expected .* to (be|equal)", re.I), 0.6),
]


def categorize(sig: FailureSignature) -> Categorization:
    """Assign a root-cause category to a signature with confidence + evidence."""
    text = f"{sig.exception_type} {sig.template} {sig.sample_message}"
    best: tuple[RootCause, float, str] | None = None
    for cause, pattern, weight in _RULES:
        m = pattern.search(text)
        if m:
            # Confidence scales with rule weight; a matched, typed exception is stronger.
            conf = min(1.0, weight * (1.0 if sig.exception_type else 0.85))
            if best is None or conf > best[1]:
                best = (cause, conf, m.group(0))
    if best is None:
        return Categorization(RootCause.UNKNOWN, 0.3, "no rule matched")
    return Categorization(best[0], round(best[1], 3), f"matched {best[0].value!r} on {best[2]!r}")
