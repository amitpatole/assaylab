"""ed25519 (asymmetric) receipts — external verification without the secret."""

from __future__ import annotations

import pytest

from assaylab.select import Candidate, select
from assaylab.select.service import attest, verify_receipt

pytest.importorskip("cryptography")  # the crypto extra


def _cands() -> list[Candidate]:
    return [Candidate(f"t{i}", q=0.5, duration_s=1.0) for i in range(3)] + \
           [Candidate(f"c{i}", q=0.001, duration_s=1.0) for i in range(20)]


def _ed_env(monkeypatch, seed_hex: str) -> None:
    monkeypatch.setenv("ASSAYLAB_ED25519_PRIVATE_KEY", seed_hex)


def test_ed25519_receipt_verifies_with_public_key(monkeypatch) -> None:
    _ed_env(monkeypatch, "11" * 16 + "22" * 16)  # 32-byte seed
    from assaylab.attest import ed25519 as ed

    sel = select(_cands(), target_epsilon=0.05)
    rec = attest(sel, _cands(), created_ts=1.0, alg="ed25519")
    assert rec.alg == "ed25519" and rec.public_key
    # A verifier with ONLY the public key (no secret) can verify.
    pub = ed.public_key_hex()
    assert verify_receipt(rec, public_key=pub)


def test_ed25519_tamper_breaks_signature(monkeypatch) -> None:
    _ed_env(monkeypatch, "33" * 16 + "44" * 16)
    sel = select(_cands(), target_epsilon=0.05)
    rec = attest(sel, _cands(), created_ts=1.0, alg="ed25519")
    pub = rec.public_key
    rec.epsilon = 0.0001  # forge a tighter bound
    assert not verify_receipt(rec, public_key=pub)


def test_ed25519_wrong_public_key_rejected(monkeypatch) -> None:
    _ed_env(monkeypatch, "55" * 16 + "66" * 16)
    sel = select(_cands(), target_epsilon=0.05)
    rec = attest(sel, _cands(), created_ts=1.0, alg="ed25519")
    # A different (attacker) public key must not verify — mismatch vs embedded key.
    other = "ab" * 32
    assert not verify_receipt(rec, public_key=other)


def test_ed25519_private_key_never_needed_to_verify(monkeypatch) -> None:
    _ed_env(monkeypatch, "77" * 16 + "88" * 16)
    from assaylab.attest import ed25519 as ed

    sel = select(_cands(), target_epsilon=0.05)
    rec = attest(sel, _cands(), created_ts=1.0, alg="ed25519")
    pub = ed.public_key_hex()
    # Clear the private key from the environment — verification still works.
    monkeypatch.delenv("ASSAYLAB_ED25519_PRIVATE_KEY", raising=False)
    monkeypatch.setattr("assaylab.attest.ed25519.user_config_dir",
                        lambda *_a, **_k: "/nonexistent-no-priv-key")
    assert verify_receipt(rec, public_key=pub)


def test_hmac_remains_the_default(monkeypatch) -> None:
    monkeypatch.setenv("ASSAYLAB_SIGNING_KEY", "hex:" + "0123456789abcdef" * 4)
    sel = select(_cands(), target_epsilon=0.05)
    rec = attest(sel, _cands(), created_ts=1.0)  # no alg -> hmac
    assert rec.alg == "hmac-sha256"
    assert verify_receipt(rec)
