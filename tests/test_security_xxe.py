"""Security regression: JUnit XML ingestion must resist XXE + entity expansion.

Pins the P1 attack surface (untrusted XML). defusedxml must refuse external
entities and billion-laughs so a malicious report can neither read local files
nor exhaust memory. A refactor that swaps in stdlib ElementTree reopens this,
so these tests fail closed.
"""

from __future__ import annotations

import pytest

from assaylab.core import ingest
from assaylab.errors import UnsafeSourceError

# Classic XXE: pull /etc/passwd into an entity referenced by a testcase name.
XXE = """<?xml version="1.0"?>
<!DOCTYPE t [ <!ENTITY xxe SYSTEM "file:///etc/passwd"> ]>
<testsuite name="s">
  <testcase classname="s.A" name="&xxe;"/>
</testsuite>"""

# Billion laughs: nested entity expansion.
BILLION = """<?xml version="1.0"?>
<!DOCTYPE lolz [
  <!ENTITY lol "lol">
  <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
  <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
]>
<testsuite name="s"><testcase classname="s.A" name="&lol3;"/></testsuite>"""


def test_xxe_external_entity_is_refused() -> None:
    with pytest.raises(UnsafeSourceError):
        ingest(XXE, backend="junit")


def test_billion_laughs_is_refused() -> None:
    with pytest.raises(UnsafeSourceError):
        ingest(BILLION, backend="junit")
