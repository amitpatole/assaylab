"""Ingestion backends: JUnit XML + outcome CSV/JSON/JSONL."""

from __future__ import annotations

import pytest

from assaylab.core import ingest
from assaylab.errors import UnsafeSourceError
from assaylab.models import Outcome

JUNIT = """<testsuite name="s" tests="3">
  <testcase classname="s.A" name="ok" time="0.1"/>
  <testcase classname="s.B" name="bad" time="0.2">
    <failure message="AssertionError: nope">trace here</failure>
  </testcase>
  <testcase classname="s.C" name="skipped"><skipped/></testcase>
</testsuite>"""


def test_junit_parses_outcomes() -> None:
    recs = ingest(JUNIT, backend="junit")
    by_id = {r.test_id: r for r in recs}
    assert by_id["s.A::ok"].outcome == Outcome.PASS
    assert by_id["s.B::bad"].outcome == Outcome.FAIL
    assert by_id["s.B::bad"].message == "AssertionError: nope"
    assert by_id["s.C::skipped"].outcome == Outcome.SKIP


def test_junit_testsuites_wrapper() -> None:
    wrapped = f"<testsuites>{JUNIT}</testsuites>"
    assert len(ingest(wrapped, backend="junit")) == 3


def test_csv_ingest_with_aliased_columns() -> None:
    csv = "test_name,status,duration\nA,passed,0.1\nB,failed,0.2\n"
    recs = ingest(csv, backend="jsonl")
    assert {r.test_id: r.outcome for r in recs} == {"A": Outcome.PASS, "B": Outcome.FAIL}


def test_json_array_ingest() -> None:
    js = '[{"test": "A", "verdict": "pass"}, {"test": "B", "verdict": "error"}]'
    recs = ingest(js, backend="jsonl")
    assert {r.test_id: r.outcome for r in recs} == {"A": Outcome.PASS, "B": Outcome.ERROR}


def test_jsonl_ingest() -> None:
    jsonl = '{"test": "A", "verdict": "pass"}\n{"test": "B", "verdict": "fail"}\n'
    recs = ingest(jsonl, backend="jsonl")
    assert len(recs) == 2


def test_inferred_backend_from_content() -> None:
    assert ingest(JUNIT)[0].test_id == "s.A::ok"  # infers junit from leading '<'


def test_oversized_inline_source_rejected() -> None:
    from assaylab.config import Settings

    tiny = Settings(max_source_bytes=10)
    with pytest.raises(UnsafeSourceError):
        ingest(JUNIT, backend="junit", settings=tiny)
