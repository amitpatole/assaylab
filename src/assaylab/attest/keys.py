"""Signing-key resolution — env, else a persisted per-installation random key.

Never a hardcoded/default secret (a shipped default key lets anyone forge a
receipt). Resolution order:

1. ``ASSAYLAB_SIGNING_KEY`` — hex, base64, or raw UTF-8 (>= 16 bytes of entropy).
2. A per-installation key persisted at ``<user_config>/assaylab/signing.key``,
   created with :func:`secrets.token_bytes` and ``0600`` perms on first use.

A malformed env key fails closed (raises) rather than silently falling back.
"""

from __future__ import annotations

import base64
import binascii
import os
import secrets
import stat
from pathlib import Path

from platformdirs import user_config_dir

from ..errors import ConfigError

_ENV = "ASSAYLAB_SIGNING_KEY"
_MIN_BYTES = 16


def _decode_env_key(raw: str) -> bytes:
    raw = raw.strip()
    # Try hex, then base64, then raw UTF-8.
    for decoder in (_try_hex, _try_b64):
        val = decoder(raw)
        if val is not None:
            if len(val) < _MIN_BYTES:
                raise ConfigError(f"{_ENV} has too little entropy (< {_MIN_BYTES} bytes)")
            return val
    val = raw.encode("utf-8")
    if len(val) < _MIN_BYTES:
        raise ConfigError(f"{_ENV} has too little entropy (< {_MIN_BYTES} bytes)")
    return val


def _try_hex(raw: str) -> bytes | None:
    try:
        if len(raw) % 2 == 0 and all(c in "0123456789abcdefABCDEF" for c in raw):
            return bytes.fromhex(raw)
    except ValueError:
        return None
    return None


def _try_b64(raw: str) -> bytes | None:
    try:
        return base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError):
        return None


def _key_path() -> Path:
    return Path(user_config_dir("assaylab")) / "signing.key"


def _load_or_create_persisted() -> bytes:
    path = _key_path()
    if path.is_file():
        data = path.read_bytes()
        if len(data) >= _MIN_BYTES:
            return data
    # Create a fresh per-installation key with restrictive perms.
    path.parent.mkdir(parents=True, exist_ok=True)
    key = secrets.token_bytes(32)
    # Write with 0600 from the start (umask-safe).
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, stat.S_IRUSR | stat.S_IWUSR)
    try:
        os.write(fd, key)
    finally:
        os.close(fd)
    return key


def resolve_key() -> bytes:
    """Return the signing key (env override, else persisted per-installation key)."""
    env = os.environ.get(_ENV)
    if env:
        return _decode_env_key(env)
    return _load_or_create_persisted()


def key_id(key: bytes) -> str:
    """A short, non-secret identifier for a key (first bytes of its SHA-256).

    Lets a receipt name *which* key signed it without revealing the key.
    """
    import hashlib

    return hashlib.sha256(key).hexdigest()[:12]
