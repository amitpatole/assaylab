"""Security regression: signing-key handling and receipt integrity.

Pins the P3 non-negotiables: no hardcoded default key, an entropy floor on
env keys, a persisted per-installation key written 0600, and constant-time
verification that a forged bound cannot pass.
"""

from __future__ import annotations

import stat

import pytest

from assaylab.attest import Receipt
from assaylab.attest.keys import _key_path, resolve_key
from assaylab.errors import ConfigError


def test_no_hardcoded_default_key_in_source() -> None:
    from pathlib import Path

    import assaylab.attest.keys as k

    src = Path(k.__file__).read_text(encoding="utf-8")
    # There must be no literal key material; keys come from env or secrets.token_bytes.
    assert "secrets.token_bytes" in src
    assert "b'default" not in src and 'b"default' not in src


def test_env_key_below_entropy_floor_is_refused(monkeypatch) -> None:
    monkeypatch.setenv("ASSAYLAB_SIGNING_KEY", "short")  # < 16 bytes
    with pytest.raises(ConfigError):
        resolve_key()


def test_env_key_hex_is_decoded(monkeypatch) -> None:
    monkeypatch.setenv("ASSAYLAB_SIGNING_KEY", "ab" * 16)  # 32 bytes hex
    assert resolve_key() == bytes.fromhex("ab" * 16)


def test_persisted_key_is_created_0600(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("ASSAYLAB_SIGNING_KEY", raising=False)
    monkeypatch.setattr("assaylab.attest.keys.user_config_dir", lambda *_a, **_k: str(tmp_path))
    key = resolve_key()
    assert len(key) >= 16
    path = _key_path()
    assert path.is_file()
    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == 0o600  # owner read/write only
    # Second call returns the same persisted key (stable identity).
    assert resolve_key() == key


def test_two_installs_differ(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("ASSAYLAB_SIGNING_KEY", raising=False)
    monkeypatch.setattr("assaylab.attest.keys.user_config_dir", lambda *_a, **_k: str(tmp_path / "a"))
    k1 = resolve_key()
    monkeypatch.setattr("assaylab.attest.keys.user_config_dir", lambda *_a, **_k: str(tmp_path / "b"))
    k2 = resolve_key()
    assert k1 != k2  # per-installation keys are independent trust domains


def test_forged_epsilon_does_not_verify() -> None:
    key = b"z" * 32
    rec = Receipt(epsilon=0.5, confidence=0.5).sign(key)
    rec.epsilon = 0.001  # attacker claims a tighter bound than was signed
    rec.confidence = 0.999
    assert not rec.verify(key)
