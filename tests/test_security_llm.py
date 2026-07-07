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


# ---- ollama provider: token exfiltration / SSRF gate (#3) -----------------

def test_ollama_refuses_token_to_untrusted_host(monkeypatch) -> None:
    from assaylab.errors import ConfigError
    from assaylab.llm.providers.ollama import OllamaProvider

    p = OllamaProvider(base_url="http://attacker.example.com:9999")
    monkeypatch.setattr(p, "_token", lambda: "SECRET-OLLAMA-TOKEN")
    monkeypatch.delenv("ASSAYLAB_OLLAMA_ALLOW_REMOTE_TOKEN", raising=False)
    import pytest

    with pytest.raises(ConfigError):
        p._auth_header()  # must refuse rather than leak the bearer token


def test_ollama_sends_token_only_to_loopback(monkeypatch) -> None:
    from assaylab.llm.providers.ollama import OllamaProvider

    p = OllamaProvider(base_url="http://127.0.0.1:11434")
    monkeypatch.setattr(p, "_token", lambda: "tok")
    assert p._auth_header() == {"Authorization": "Bearer tok"}


def test_ollama_remote_https_requires_explicit_optin(monkeypatch) -> None:
    from assaylab.llm.providers.ollama import OllamaProvider

    p = OllamaProvider(base_url="https://ollama.mycorp.com")
    monkeypatch.setattr(p, "_token", lambda: "tok")
    monkeypatch.setenv("ASSAYLAB_OLLAMA_ALLOW_REMOTE_TOKEN", "1")
    assert p._auth_header() == {"Authorization": "Bearer tok"}
    monkeypatch.delenv("ASSAYLAB_OLLAMA_ALLOW_REMOTE_TOKEN")
    import pytest

    from assaylab.errors import ConfigError

    with pytest.raises(ConfigError):
        p._auth_header()  # https without opt-in still refuses
