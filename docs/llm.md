# Test generation & self-healing

`assaylab` can propose a regression test from a failure signature, or a
mitigation for a flaky one — but it **never executes or applies LLM-authored
code**. A proposal is a dry-run artifact; you run it in your own sandbox, and
acceptance is decided by grading that run through the verdict layer.

!!! warning "The core guardrail"
    assaylab does not `exec`, `eval`, `subprocess`, or auto-apply generated
    content. A generated test is trusted only once a real run shows it
    *reproduces* the failure; a heal only once the flaky signature *stops
    failing*. This is enforced by regression tests, not just convention.

## The gated loop

```console
$ assaylab generate fail.xml --provider template -o proposal.json   # DRY-RUN, key-free
[test_generation] regression test for NullPointerException (3afa5a8635b5)
  provider=template model=- prompt_sha=8d99eb624ccd8506 applied=False
  acceptance: {'check': 'reproduces', 'target_test': 'svc.Payment::test_charge', ...}
  --- proposed content (DRY-RUN, not executed) ---
  ...

# You review + run the proposal in YOUR sandbox, then feed the result back:
$ assaylab accept proposal.json fail.xml     # a run where it reproduced
ACCEPTED: generated test reproduced the failure (svc.Payment::test_charge)

$ assaylab accept proposal.json pass.xml     # a run where it did not
REJECTED: generated test did NOT reproduce the failure (svc.Payment::test_charge)
```

`accept` exits non-zero when a proposal is rejected, so it gates cleanly.

Self-healing is the same shape:

```console
$ assaylab heal history.csv --provider template -o heal.json   # propose a mitigation (dry-run)
$ assaylab accept heal.json rerun.xml                          # accepted iff the signature stopped failing
```

## Providers

| Provider | Needs | Notes |
|---|---|---|
| `template` | nothing | Deterministic, key-free. Default; used in demos/tests/CI. |
| `claude` | `pip install assaylab[llm]`, `ANTHROPIC_API_KEY` | Anthropic SDK; defaults to the most capable model. |
| `ollama` | `pip install assaylab[llm]` | Local or hosted; token from `~/.config/ollama/key`. |

Keys resolve from the environment or `~/.config` — never hardcoded, never
logged. Completions are size-capped and network calls timeout-bounded.

## Provenance

Every `Proposal` records `provider`, `model`, a `prompt_sha`, the acceptance
criterion, and `applied` (always `False`). It serializes to JSON so a proposal
is auditable and reproducible.
