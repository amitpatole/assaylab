# assaylab

**Validation intelligence for CI.** Attested test-selection with verifiable
confidence bounds, failure-signature root-cause analysis, and analytics that
support data-driven engineering decisions.

> **Status:** P1 shipped — ingest + failure-signature clustering, graded on the
> `agentsensory` contract. RCA/forecasting (P2), attested selection (P3) and the
> dashboard (P4) follow.

## Try it (no API key, no network)

```console
$ pipx install assaylab            # or: uv tool install assaylab
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

The two `NullPointerException` failures cluster into **one** signature despite
differing memory addresses — that is the failure-signature engine at work.

Grade your own CI output (exits non-zero on FAIL, so it drops into a gate):

```console
$ assaylab check path/to/junit.xml           # JUnit/xUnit XML
$ assaylab check results.csv --baseline prev.csv   # flag NEW failures vs a baseline
$ assaylab signatures junit.xml              # list failure signatures, most frequent first
$ assaylab perceive junit.xml                # brain-facing Handoff (JSON)
```

## What it does (planned)

**Validation intelligence & analytics**
- Failure-signature clustering over historical CI/test results.
- Automated root-cause analysis and flaky-vs-real classification.
- Predictive failure forecasting and risk identification.
- A dashboard for data-driven engineering decisions.

**Test optimization**
- Risk-based test selection and prioritization from code-change diffs.
- Coverage-gap and redundancy detection.
- Runtime reduction that **preserves a stated confidence bound**.

**Automation**
- LLM-assisted test generation from requirements and code changes.
- Adaptive / self-healing execution, gated behind a verdict layer.

## The distinctive idea

Most test-optimization tools give you a speedup and ask you to trust it.
`assaylab` emits a **signed receipt that bounds the confidence lost** when it
reduces a suite: *ran subset S → probability of missing regression-class C ≤ ε*,
with an attested, checkable proof. Speedup **with** a formal confidence claim.

Verdicts follow the `agentsensory` contract (Report = verdict + grounded issues
+ Handoff), so results are portable and auditable.

MIT © 2026 Amit Patole

*— amitpatole*
