# Changelog

All notable changes to assaylab are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/); versions follow SemVer.

## [Unreleased] — P5: LLM-assisted test generation & self-healing (gated)

### Added
- **LLM providers** (`assaylab.llm`) behind the `llm` extra: `claude` (Anthropic
  SDK, `claude-opus-4-8` default, key from `ANTHROPIC_API_KEY`) and `ollama`
  (local/hosted). A deterministic **`template` provider** needs no API key, so
  the whole flow runs key-free in demos/tests/CI.
- **Test generation** (`propose_test`) and **self-healing** (`propose_heal`) —
  each emits a dry-run `Proposal` with provenance (provider, model, prompt hash)
  and an acceptance criterion.
- **The gate** (`evaluate_proposal`) — acceptance flows through the verdict
  layer: a generated test counts only if a real run shows it *reproduces* the
  failure; a heal counts only if the flaky signature *stops failing*.
- **CLI**: `generate`, `heal` (both DRY-RUN), `accept` (grade a real run against
  a proposal; non-zero if rejected).

### Security
- **assaylab never executes or applies LLM-authored code.** Proposals are
  artifacts a human/CI runs in their own sandbox (per the org guardrail:
  isolate agent-generated code, never in-process `exec`). Pinned by
  `test_security_llm.py`: no `exec`/`eval`/`subprocess`/`compile` over generated
  content, `applied` is always False, the gate reads test output (not proposal
  content), and generate/heal never write or apply files. API keys resolve from
  env/`~/.config`, never hardcoded or logged; completions are size-capped and
  network calls timeout-bounded.

## [Unreleased] — P4: validation-intelligence dashboard (Warm Paper)

### Added
- **Self-contained HTML report** (`assaylab.dashboard.build_report`, CLI
  `assaylab report`) — verdict, failure signatures + root cause, riskiest
  tests, and the **confidence/speedup frontier** as a dependency-free inline
  SVG. No server, no network (branded fonts load progressively, degrade to
  system stacks). Warm Paper design system; accent is a desaturated
  validation-green; carries the `— amitpatole` maker's mark.
- All dynamic text is HTML-escaped — untrusted test messages cannot inject
  markup (XSS regression test pins this).
- `infer_backend` now treats non-`<` inline content as `jsonl` (CSV/JSON), so
  inline outcome logs parse correctly.

## [Unreleased] — P3: attested test-selection with a verifiable confidence bound

### Added
- **Selection engine** (`assaylab.select`) — each candidate test has a
  detection probability `q` (from P2 forecast); skipping set `U` costs
  confidence `epsilon = 1 - prod(1-q)`. Greedy keep by value-density (`q`/sec)
  until `target_epsilon` is met or `time_budget_s` is spent. Code-touched tests
  can be force-kept. Reports speedup + achieved confidence.
- **Attested receipt** (`assaylab.attest`) — HMAC-SHA256 over the *outcome*
  (inputs hash, selected/skipped hashes, and the computed `epsilon`), so the
  signature binds the real result. Constant-time verify. Signing key resolves
  env → persisted per-installation key (`0600`), **never a hardcoded default**.
- **Reproduction verification** (`verify_reproduction`) — because selection is
  deterministic in its committed inputs, a consumer re-runs it to confirm the
  bound is *genuine*, not merely signed.
- **CLI**: `select` (subset + signed receipt), `verify` (signature; `--against`
  recomputes the bound from history).
- Security regression tests: no default key, entropy floor, `0600` key file,
  per-install key independence, tamper/forgery detection, inert receipt load.

### Security
- Ran the forge-a-tighter-bound exploit against the built code: a tampered
  `epsilon` fails both signature verification and reproduction. Pinned by tests.

## [Unreleased] — P2: ML-based root-cause analysis

### Added
- **Root-cause categorization** (`assaylab.rca.categorize`) — transparent,
  always-on classifier mapping a signature to a cause (null-deref, timeout,
  dependency, config, resource, concurrency, network, assertion, …) with a
  confidence and the evidence that fired.
- **Flaky-vs-real classification** (`assaylab.rca.flaky`) — history-aware:
  same-commit pass+fail (order-agnostic flakiness) and flip-rate. An all-flaky
  failure set grades **WARN** (not FAIL), so flakiness doesn't block the gate.
- **Risk + forecast** (`assaylab.rca.risk`) — per-test risk (recency-weighted
  fail-rate blended with flip-rate) and next-run failure forecast; `rank_risk`.
- **Learned model** (`assaylab.rca.model.LogisticModel`) — a self-contained,
  pure-Python logistic regression (deterministic batch gradient descent) for
  flaky prediction. Serialized to **JSON, never pickle** (inert load — no code
  execution on a model pulled from a registry/CI). `assaylab train` fits it.
- **CLI**: `rca` (categorize + flaky + risk, non-zero on FAIL), `risk` (rank
  tests), `train` (fit the JSON model).
- Security regression tests pinning inert model loading (JSON-only, size-capped,
  schema-checked, no pickle).

## [0.1.0] — P1: ingest + failure-signature clustering

### Added
- **Ingestion** (`assaylab.ingest`) with pluggable backends:
  - `junit` — JUnit/xUnit XML (pytest, Maven Surefire, Gradle), parsed with
    `defusedxml` (XXE / billion-laughs closed, size-capped before read).
  - `jsonl` — outcome CSV / JSON array / JSONL, mapping the common
    `(project, commit, test_id, run_id, verdict, duration)` schema used by
    FlakeFlagger / RTPTorrent / TravisTorrent exports.
  - Entry-point group `assaylab.backends` for third-party backends.
- **Failure-signature clustering** (`assaylab.cluster`) — normalizes away
  incidental variation (addresses, line numbers, temp paths, timestamps, UUIDs,
  numbers) and fingerprints failures so distinct runs of the same root collapse.
- **Grading** into the `agentsensory` contract: `Report` = verdict + grounded
  issues + `Handoff`. Optional `--baseline` flags signatures absent from a prior
  run as `NEW_FAILURE`.
- **CLI** (`assaylab`): `check` (CI gate, non-zero on FAIL), `signatures`,
  `perceive`, `demo` (broken → FAIL → fixed → PASS, no API key), `doctor`.
- Security regression tests pinning XXE + billion-laughs refusal.

### Notes
- Contract-compatible with `agentsensory` (imported, never redefined).
- Base wheel is light; REST / MCP / dataset-fetch live behind extras.
