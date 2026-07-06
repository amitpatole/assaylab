"""Security regression: assaylab must never execute or apply LLM-authored code.

The core guardrail for P5. LLM output is a dry-run artifact; only a human/CI
runs it, in their own sandbox. These tests fail closed if someone wires an
exec/eval/subprocess path over generated content, or flips a proposal to
auto-applied.
"""

from __future__ import annotations

from pathlib import Path

import assaylab.llm.gate as gate_mod
import assaylab.llm.generate as gen_mod
import assaylab.llm.heal as heal_mod
from assaylab.llm import propose_test
from assaylab.models import FailureSignature


def _sig() -> FailureSignature:
    return FailureSignature(signature_id="s", template="boom", exception_type="E",
                            tests=["t"], count=1, sample_message="boom")


def test_proposal_is_never_marked_applied() -> None:
    assert propose_test(_sig(), provider="template", created_ts=1.0).applied is False


def test_llm_modules_do_not_execute_generated_code() -> None:
    # No dynamic execution or process spawning anywhere in the llm package.
    pkg_dir = Path(gen_mod.__file__).parent
    forbidden = ("exec(", "eval(", "subprocess", "os.system", "compile(", "runpy")
    offenders = []
    for py in pkg_dir.rglob("*.py"):
        src = py.read_text(encoding="utf-8")
        for token in forbidden:
            if token in src:
                offenders.append(f"{py.name}:{token}")
    assert not offenders, f"llm package must not execute code: {offenders}"


def test_gate_only_reads_test_output_never_runs_content() -> None:
    # The gate's input is a *result* source (test output), not the proposal content.
    src = Path(gate_mod.__file__).read_text(encoding="utf-8")
    assert "ingest(result_source" in src  # it ingests a run, does not run the proposal
    assert "proposal.content" not in src  # content is never touched by the gate


def test_generate_and_heal_do_not_write_or_apply_files() -> None:
    for mod in (gen_mod, heal_mod):
        src = Path(mod.__file__).read_text(encoding="utf-8")
        assert "write_text" not in src and "open(" not in src
