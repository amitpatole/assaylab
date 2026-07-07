"""Ingestion backend protocol: read a source into normalized :class:`TestRecord`s."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from ..config import Settings
from ..errors import UnsafeSourceError
from ..models import TestRecord


@runtime_checkable
class ResultsBackend(Protocol):
    """A source of test-execution records (JUnit XML, outcome CSV/JSONL, …)."""

    name: str

    def available(self) -> bool:
        """True when this backend's dependencies are importable."""
        ...

    def parse(self, source: str, *, settings: Settings) -> list[TestRecord]:
        """Parse ``source`` (a path or inline text) into records.

        Raises :class:`UnsafeSourceError` on oversized / malformed input.
        """
        ...


def read_source(source: str, *, settings: Settings) -> str:
    """Read ``source`` as text, enforcing the byte cap *before* allocation.

    ``source`` is treated as a filesystem path when it points at an existing
    file; otherwise it is treated as inline content. The cap is enforced by
    reading at most ``cap`` bytes and refusing if more remain — not by a prior
    ``stat`` (which a concurrent writer could grow past between check and read).
    """
    cap = settings.max_source_bytes
    p = Path(source)
    try:
        is_file = p.is_file()
    except OSError:
        is_file = False
    if is_file:
        with p.open("rb") as f:
            data = f.read(cap + 1)  # read one byte past the cap to detect overflow
        if len(data) > cap:
            raise UnsafeSourceError(f"source exceeds size cap (> {cap} bytes)")
        return data.decode("utf-8", errors="replace")
    if len(source.encode("utf-8", "replace")) > cap:
        raise UnsafeSourceError("inline source exceeds size cap")
    return source
