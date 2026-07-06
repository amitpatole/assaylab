# assaylab

**Validation intelligence for CI.** Attested test-selection with verifiable
confidence bounds, failure-signature root-cause analysis, and analytics that
support data-driven engineering decisions.

> **Status:** P1–P5 shipped — ingest + failure-signature clustering (P1),
> ML root-cause analysis + flaky-vs-real + risk (P2), attested test-selection
> with a verifiable confidence bound (P3), the Warm Paper dashboard (P4), and
> gated LLM-assisted test generation / self-healing (P5).

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

### Root-cause analysis (P2)

Point `rca` at run history (many runs, ideally with commit + outcome) to get a
root-cause category, a flaky-vs-real verdict, and a risk score per signature.
An all-flaky failure set grades **WARN** so flakiness doesn't fail your gate:

```console
$ assaylab rca history.csv
verdict: FAIL  —  4 failing execution(s) across 2 signature(s) (1 real, 1 flaky); 4/8 passed.
  [error]   failure_signature  cause=null_deref (conf 1.0)  flaky=False  risk=0.7
  [warning] flaky_suspect      cause=timeout   (conf 0.85) flaky=True (p=0.95)  risk=0.53

$ assaylab risk history.csv --top 5          # rank tests by failure risk + forecast
$ assaylab train labeled.csv -o flaky.json   # fit the flaky model (JSON, never pickle)
$ assaylab rca history.csv --model flaky.json  # use the learned model
```

The flaky model is a pure-Python logistic regression persisted as JSON — no
heavy ML dependency, and loading a model can't execute code.

### Attested test-selection with a verifiable confidence bound (P3)

The distinctive idea: reduce the suite **and** emit a signed receipt that bounds
the confidence lost. Each test `t` gets a detection probability `q_t`; skipping
set `U` costs `ε = 1 − Π(1 − q_t)` — the chance a skipped test would have caught
a regression. Keep the highest value-density tests until `ε ≤ target`:

```console
$ export ASSAYLAB_SIGNING_KEY=$(python -c "import secrets;print(secrets.token_hex(32))")
$ assaylab select history.csv --target-epsilon 0.05 --receipt receipt.json
selected 3/43 tests  speedup 9.0x  confidence 1.0000  (epsilon 0.0000)
  run:  svc.Hot::t0, svc.Hot::t1, svc.Hot::t2
  wrote signed receipt -> receipt.json

$ assaylab verify receipt.json --against history.csv
receipt a1460d1de5ee: signature VALID  (epsilon 0.0000, confidence 1.0000, selected 3/43, speedup 9.0x)
  reproduction: OK — reproduced: selection and confidence bound are genuine
```

Tamper with the receipt's `epsilon` and verification fails closed — the
signature binds the actual bound, and `--against` re-derives it from the inputs.

**Honest limits** (the receipt's residual assumptions, not guarantees):
independence of test failures, `q_t` stationarity, and coverage only of
regression classes seen historically. HMAC is a symmetric trust domain
(verifier holds the key); asymmetric (ed25519) signatures are future work.

### Dashboard (P4)

One self-contained HTML report — verdict, failure signatures + root cause,
riskiest tests, and the confidence/speedup frontier as an inline SVG. No server,
no network; Warm Paper design system.

```console
$ assaylab report history.csv -o report.html --title "checkout service"
wrote dashboard -> report.html
```

### LLM-assisted test generation & self-healing (P5)

`assaylab` proposes a regression test (or a flaky mitigation) from a failure
signature — but it **never executes or applies the generated code**. The
proposal is a dry-run artifact; you run it in your own sandbox, and acceptance
is decided by grading that run through the verdict layer:

```console
$ assaylab generate fail.xml --provider template -o proposal.json   # DRY-RUN (key-free)
$ assaylab accept proposal.json fail.xml       # a real run that reproduces -> ACCEPTED (exit 0)
$ assaylab accept proposal.json pass.xml       # does not reproduce      -> REJECTED (exit 1)
```

Providers: `template` (deterministic, no key), `claude` (`pip install
assaylab[llm]`, `ANTHROPIC_API_KEY`), `ollama` (local/hosted). A generated test
is only trusted once it demonstrably reproduces the bug; a heal only once the
flaky signature stops failing.

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
