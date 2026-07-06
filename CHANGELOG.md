# Changelog

All notable changes to assaylab are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/); versions follow SemVer.

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
