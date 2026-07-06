"""Outcome CSV / JSON / JSONL ingestion.

Maps the common ``(project, commit, test_id, run_id, verdict, duration)`` shape
that FlakeFlagger / RTPTorrent / TravisTorrent CSVs and most home-grown test
loggers export. Accepts:

* a JSON array of record objects,
* JSON Lines (one object per line),
* CSV with a header row.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from ..config import Settings
from ..errors import UnsafeSourceError
from ..models import Outcome, TestRecord
from .base import read_source

# Accept several column spellings for the same field.
_ALIASES: dict[str, tuple[str, ...]] = {
    "test_id": ("test_id", "test", "test_name", "name", "testName"),
    "outcome": ("outcome", "verdict", "status", "result"),
    "project": ("project", "repo", "gh_project_name"),
    "commit": ("commit", "sha", "git_commit", "gh_commit"),
    "run_id": ("run_id", "build", "build_id", "run"),
    "duration_s": ("duration_s", "duration", "time", "elapsed"),
    "file": ("file", "path", "module"),
    "message": ("message", "msg", "error_message"),
    "stacktrace": ("stacktrace", "trace", "traceback", "stack"),
}

_OUTCOME_MAP = {
    "pass": Outcome.PASS, "passed": Outcome.PASS, "ok": Outcome.PASS, "success": Outcome.PASS,
    "true": Outcome.PASS, "1": Outcome.PASS,
    "fail": Outcome.FAIL, "failed": Outcome.FAIL, "failure": Outcome.FAIL,
    "false": Outcome.FAIL, "0": Outcome.FAIL,
    "error": Outcome.ERROR, "errored": Outcome.ERROR,
    "skip": Outcome.SKIP, "skipped": Outcome.SKIP,
}


class JsonlBackend:
    """Parse JSON array / JSONL / CSV outcome logs into records."""

    name = "jsonl"

    def available(self) -> bool:
        return True

    def parse(self, source: str, *, settings: Settings | None = None) -> list[TestRecord]:
        settings = settings or Settings()
        text = read_source(source, settings=settings)
        rows = _rows(text)
        records: list[TestRecord] = []
        for row in rows:
            records.append(_row_to_record(row))
            if len(records) > settings.max_records:
                raise UnsafeSourceError("record count exceeds cap")
        return records


def _rows(text: str) -> list[dict[str, Any]]:
    stripped = text.lstrip()
    if stripped.startswith("["):
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError as e:
            raise UnsafeSourceError(f"malformed JSON array: {e}") from None
        if not isinstance(data, list):
            raise UnsafeSourceError("expected a JSON array of records")
        return [r for r in data if isinstance(r, dict)]
    if stripped.startswith("{"):
        # JSON Lines
        out: list[dict[str, Any]] = []
        for line in stripped.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                raise UnsafeSourceError(f"malformed JSONL line: {e}") from None
            if isinstance(obj, dict):
                out.append(obj)
        return out
    # CSV
    reader = csv.DictReader(io.StringIO(text))
    return [dict(r) for r in reader]


def _pick(row: dict[str, Any], field: str) -> Any:
    for alias in _ALIASES[field]:
        if alias in row and row[alias] not in (None, ""):
            return row[alias]
    return None


def _row_to_record(row: dict[str, Any]) -> TestRecord:
    raw_outcome = str(_pick(row, "outcome") or "").strip().lower()
    outcome = _OUTCOME_MAP.get(raw_outcome, Outcome.FAIL if raw_outcome else Outcome.PASS)
    dur = _pick(row, "duration_s")
    try:
        duration = float(dur) if dur is not None else 0.0
    except (ValueError, TypeError):
        duration = 0.0
    return TestRecord(
        test_id=str(_pick(row, "test_id") or "<unknown>"),
        outcome=outcome,
        project=str(_pick(row, "project") or ""),
        commit=str(_pick(row, "commit") or ""),
        run_id=str(_pick(row, "run_id") or ""),
        duration_s=duration,
        file=(str(_pick(row, "file")) if _pick(row, "file") else None),
        message=str(_pick(row, "message") or ""),
        stacktrace=str(_pick(row, "stacktrace") or ""),
    )
