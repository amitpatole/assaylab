"""JUnit XML ingestion — the CI-native format (pytest, Maven Surefire, Gradle, …).

Security: parsed with :mod:`defusedxml`, which disables external-entity and DTD
processing, closing XXE and billion-laughs. Input is size-capped before read.
"""

from __future__ import annotations

from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import ParseError, fromstring

from ..config import Settings
from ..errors import UnsafeSourceError
from ..models import Outcome, TestRecord
from .base import read_source


class JUnitBackend:
    """Parse JUnit/xUnit ``<testsuite>``/``<testcase>`` XML into records."""

    name = "junit"

    def available(self) -> bool:
        return True

    def parse(self, source: str, *, settings: Settings | None = None) -> list[TestRecord]:
        settings = settings or Settings()
        text = read_source(source, settings=settings)
        try:
            root = fromstring(text)
        except DefusedXmlException:
            # External entities / DTD / entity-expansion were refused — fail closed.
            raise UnsafeSourceError("unsafe XML rejected (entities/DTD forbidden)") from None
        except ParseError as e:
            raise UnsafeSourceError(f"malformed JUnit XML: {e}") from None

        records: list[TestRecord] = []
        # A file may be a single <testsuite> or a <testsuites> wrapper.
        suites = root.iter("testsuite")
        for suite in suites:
            suite_name = suite.get("name", "")
            for case in suite.findall("testcase"):
                records.append(_case_to_record(case, suite_name))
                if len(records) > settings.max_records:
                    raise UnsafeSourceError("record count exceeds cap")
        return records


def _case_to_record(case, suite_name: str) -> TestRecord:  # type: ignore[no-untyped-def]
    classname = case.get("classname", "") or suite_name
    name = case.get("name", "")
    test_id = f"{classname}::{name}" if classname else name

    outcome = Outcome.PASS
    message = ""
    stacktrace = ""
    # <failure>/<error> mark a failing case; <skipped> marks a skip.
    for tag, oc in (("error", Outcome.ERROR), ("failure", Outcome.FAIL)):
        el = case.find(tag)
        if el is not None:
            outcome = oc
            message = (el.get("message") or "").strip()
            stacktrace = (el.text or "").strip()
            break
    else:
        if case.find("skipped") is not None:
            outcome = Outcome.SKIP

    try:
        duration = float(case.get("time", "0") or 0)
    except ValueError:
        duration = 0.0

    return TestRecord(
        test_id=test_id or "<unknown>",
        outcome=outcome,
        duration_s=duration,
        file=case.get("file"),
        line=_int_or_none(case.get("line")),
        message=message,
        stacktrace=stacktrace,
    )


def _int_or_none(v: str | None) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except ValueError:
        return None
