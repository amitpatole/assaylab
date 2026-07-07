# assaylab

**Validation intelligence for CI.** `assaylab` turns raw test/CI output into a
graded verdict: it clusters failures into *signatures*, assigns a root cause,
tells real failures from flaky ones, scores per-test risk, and can reduce a test
suite while emitting a **signed, verifiable confidence bound** on what was
skipped.

Every result speaks the [`agentsensory`](https://github.com/amitpatole/agentsensory)
contract — a `Report` of `pass` / `warn` / `fail` + grounded issues + a
`Handoff` — so verdicts are portable and auditable.

## The distinctive idea

Most test-optimization tools give you a speedup and ask you to trust it.
`assaylab` reduces a suite **and** emits a signed receipt that bounds the
confidence lost:

> ran subset *S* → probability a skipped test would have caught a regression
> ≤ ε, here's the attested, re-derivable proof.

## What it does

| Area | Capability |
|---|---|
| **Signatures** | Cluster failures that share a root, ignoring incidental variation (addresses, line numbers, temp paths, timestamps). |
| **Root cause** | Categorize each signature (null-deref, timeout, dependency, config, …) with confidence + evidence. |
| **Flaky-vs-real** | Same-commit pass+fail and flip-rate; a learned logistic model. All-flaky failures grade **WARN**, not FAIL. |
| **Risk & forecast** | Per-test recency-weighted failure rate + next-run forecast. |
| **Attested selection** | Risk-based subset with a signed, re-derivable confidence bound. |
| **Dashboard** | A self-contained HTML report with the confidence/speedup frontier. |
| **Test generation** | LLM-assisted regression tests and flaky mitigations — dry-run, gated behind the verdict layer, never auto-executed. |

## Install

```console
$ pip install assaylab            # base wheel is light
$ pip install "assaylab[llm]"     # + claude/ollama providers
```

Try it with no API key and no network:

```console
$ assaylab demo
```

MIT © Amit Patole · *— amitpatole*
