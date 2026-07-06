# Changelog

All notable changes to assaylab are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/); versions follow SemVer.

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
