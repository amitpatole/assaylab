"""Signing-key resolution — env, else a persisted per-installation random key.

Never a hardcoded/default secret (a shipped default key lets anyone forge a
receipt). Resolution order:

1. ``ASSAYLAB_SIGNING_KEY`` — an **explicitly encoded** key: ``hex:<hex>``,
   ``base64:<b64>``, or ``raw:<utf8>`` (or a bare value, treated as raw). The
   encoding is never guessed, so one string can't resolve to two different keys.
   Must carry >= 16 bytes and not be a degenerate (single-byte-repeated) value.
2. A per-installation key persisted at ``<user_config>/assaylab/signing.key``,
   created with :func:`secrets.token_bytes` and ``0600`` perms on first use.

Both paths **refuse to follow symlinks and reject files not owned by the
current user**, closing the symlink/TOCTOU forgery vector. A malformed env key
fails closed (raises) rather than silently falling back.
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


def _reject_degenerate(val: bytes) -> None:
    if len(val) < _MIN_BYTES:
        raise ConfigError(f"{_ENV} has too little entropy (< {_MIN_BYTES} bytes)")
    if len(set(val)) < 4:
        raise ConfigError(f"{_ENV} is degenerate (too few distinct bytes) — use a random key")


def _decode_env_key(raw: str) -> bytes:
    """Decode an explicitly-scheme-prefixed key. No guessing between encodings."""
    raw = raw.strip()
    if raw.startswith("hex:"):
        try:
            val = bytes.fromhex(raw[4:])
        except ValueError as e:
            raise ConfigError(f"{_ENV} has a 'hex:' prefix but invalid hex: {e}") from None
    elif raw.startswith("base64:"):
        try:
            val = base64.b64decode(raw[7:], validate=True)
        except (binascii.Error, ValueError) as e:
            raise ConfigError(f"{_ENV} has a 'base64:' prefix but invalid base64: {e}") from None
    elif raw.startswith("raw:"):
        val = raw[4:].encode("utf-8")
    else:
        # Unprefixed: treated as raw bytes (never re-interpreted as hex/base64).
        val = raw.encode("utf-8")
    _reject_degenerate(val)
    return val


_O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)  # 0 on platforms without it (e.g. Windows)


def _key_path() -> Path:
    return Path(user_config_dir("assaylab")) / "signing.key"


def _reject_symlinked_ancestors(path: Path) -> None:
    """Fail closed if any existing ancestor of ``path`` is a symlink (Finding 2).

    ``O_NOFOLLOW`` only guards the final component; a symlinked *parent* could
    still redirect the read/create. We walk the ancestors and refuse any symlink.
    """
    for parent in path.parents:
        if parent.is_symlink():
            raise ConfigError(f"refusing signing key under symlinked directory {parent}")
        if not parent.exists():
            continue


def _owned_by_us(st: os.stat_result) -> bool:
    geteuid = getattr(os, "geteuid", None)
    return geteuid is None or st.st_uid == geteuid()


def _open_no_symlink_read(path: Path) -> bytes | None:
    """Read a regular, owner-owned file without following symlinks. None if absent."""
    _reject_symlinked_ancestors(path)
    try:
        fd = os.open(str(path), os.O_RDONLY | _O_NOFOLLOW)
    except FileNotFoundError:
        return None
    except OSError as e:
        # ELOOP: the path is a symlink — refuse it rather than reading through.
        raise ConfigError(f"signing key at {path} is a symlink or unreadable — refusing") from e
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise ConfigError(f"signing key at {path} is not a regular file — refusing")
        if not _owned_by_us(st):
            raise ConfigError(f"signing key at {path} is not owned by the current user — refusing")
        if st.st_size > 4096:  # a key is 32 bytes; anything large is wrong
            raise ConfigError(f"signing key at {path} is implausibly large — refusing")
        return os.read(fd, 4096)
    finally:
        os.close(fd)


def _load_or_create_persisted() -> bytes:
    path = _key_path()
    data = _open_no_symlink_read(path)
    if data is not None and len(data) >= _MIN_BYTES:
        return data

    # Create fresh. mkdir the parent 0700, then O_CREAT|O_EXCL|O_NOFOLLOW 0600 so
    # a pre-planted symlink or file can't be followed/reused (H1).
    path.parent.mkdir(parents=True, exist_ok=True)
    _reject_symlinked_ancestors(path)  # no symlinked ancestor may redirect the write (Finding 2)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    key = secrets.token_bytes(32)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | _O_NOFOLLOW
    try:
        fd = os.open(str(path), flags, stat.S_IRUSR | stat.S_IWUSR)
    except FileExistsError:
        # Something raced us (or a symlink is squatting the path). Re-read safely;
        # if that still doesn't yield a usable owned key, fail closed.
        data = _open_no_symlink_read(path)
        if data is not None and len(data) >= _MIN_BYTES:
            return data
        raise ConfigError(f"could not create signing key at {path} — path is occupied") from None
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
