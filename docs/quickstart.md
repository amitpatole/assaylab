# Quickstart

Everything here runs with **no API key and no network**.

## The demo

`assaylab demo` grades a synthetic broken suite, then its fix:

```console
$ assaylab demo
assaylab demo — a synthetic suite graded, then its fix (no API key, no network)

1) broken suite:
verdict: FAIL  —  3 failing execution(s) across 2 signature(s); 1/4 passed.
  [error] failure_signature: NullPointerException across 2 tests (2 runs): ...
      tests: checkout.PaymentTest::test_charge, checkout.RefundTest::test_refund
      signature: 4926f0502c1b  files: checkout/pay.py
  [error] failure_signature: AssertionError across 1 test (1 run): ...
      tests: checkout.CartTest::test_total
      signature: 81ddd6026e88  files: checkout/cart.py

2) after the fix:
verdict: PASS  —  4/4 tests passed — no failure signatures.
```

The two `NullPointerException` failures cluster into **one** signature even
though their memory addresses differ — that is the failure-signature engine
collapsing incidental variation.

## Grade your own CI output

`check` exits non-zero on FAIL, so it drops straight into a CI gate:

```console
$ assaylab check path/to/junit.xml            # JUnit / xUnit XML
$ assaylab check results.csv --baseline prev.csv   # flag NEW failures vs a baseline
$ assaylab signatures junit.xml               # list signatures, most frequent first
$ assaylab perceive junit.xml                 # brain-facing Handoff (JSON)
```

Ingestion accepts **JUnit/xUnit XML** (pytest, Maven Surefire, Gradle) and
**outcome CSV / JSON / JSONL** with the common
`(project, commit, test_id, run_id, verdict, duration)` shape.

## Check the install

```console
$ assaylab doctor
[ok ] agentsensory contract: v0.1.0
[ok ] safe XML (defusedxml): installed
[ok ] junit backend: JUnit/xUnit XML (built-in)
[ok ] jsonl backend: CSV/JSON/JSONL outcomes (built-in)
[MISS] LLM (claude): not installed — pip install assaylab[llm]
```

## As a library

```python
import asyncio
from assaylab import analyze

report = asyncio.run(analyze("path/to/junit.xml", backend="junit"))
print(report.verdict.value, report.summary)
handoff = report.to_handoff()   # the agentsensory Handoff for a brain
```
