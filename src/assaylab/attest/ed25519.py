"""ed25519 (asymmetric) signing for receipts — the ``crypto`` extra.

HMAC receipts are a *symmetric* trust domain: the verifier needs the signing
key, so it can also forge. ed25519 closes that — the producer signs with a
private key and publishes the public key; anyone can verify against the (trusted,
out-of-band) public key without being able to sign. This makes "an external
consumer verifies" real.

Private key resolution mirrors the HMAC key: env ``ASSAYLAB_ED25519_PRIVATE_KEY``
(hex or base64 of the 32-byte seed), else a persisted per-installation key at
``<user_config>/assaylab/ed25519.key`` (created ``0600``, symlink-guarded like
the HMAC key). The verifier only ever needs the public key.
"""

from __future__ import annotations

import base64
import binascii
import os
import stat
from pathlib import Path

from platformdirs import user_config_dir

from ..errors import ConfigError, MissingDependencyError

_ENV = "ASSAYLAB_ED25519_PRIVATE_KEY"
_O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)


def _load_cryptography():  # type: ignore[no-untyped-def]
    try:
        from cryptography.hazmat.primitives.asymmetric import ed25519
    except ImportError as e:
        raise MissingDependencyError(
            "ed25519 receipts need the cryptography package; pip install assaylab[crypto]"
        ) from e
    return ed25519


def _decode_seed(raw: str) -> bytes:
    raw = raw.strip()
    for dec in (lambda s: bytes.fromhex(s), lambda s: base64.b64decode(s, validate=True)):
        try:
            val = dec(raw)
        except (ValueError, binascii.Error):
            continue
        if len(val) == 32:
            return val
    raise ConfigError(f"{_ENV} must be 32 bytes as hex or base64")


def _key_path() -> Path:
    return Path(user_config_dir("assaylab")) / "ed25519.key"


def _load_or_create_seed() -> bytes:
    path = _key_path()
    try:
        fd = os.open(str(path), os.O_RDONLY | _O_NOFOLLOW)
    except FileNotFoundError:
        fd = None
    except OSError as e:
        raise ConfigError(f"ed25519 key at {path} is a symlink or unreadable — refusing") from e
    if fd is not None:
        try:
            st = os.fstat(fd)
            geteuid = getattr(os, "geteuid", None)
            if not stat.S_ISREG(st.st_mode) or (geteuid and st.st_uid != geteuid()):
                raise ConfigError(f"ed25519 key at {path} is not a regular owned file — refusing")
            data = os.read(fd, 64)
            if len(data) >= 32:
                return data[:32]
        finally:
            os.close(fd)
    ed25519 = _load_cryptography()
    seed = ed25519.Ed25519PrivateKey.generate().private_bytes_raw()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    newfd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL | _O_NOFOLLOW,
                    stat.S_IRUSR | stat.S_IWUSR)
    try:
        os.write(newfd, seed)
    finally:
        os.close(newfd)
    return seed


def resolve_private_key():  # type: ignore[no-untyped-def]
    """Return an Ed25519PrivateKey (env seed, else persisted per-install seed)."""
    ed25519 = _load_cryptography()
    env = os.environ.get(_ENV)
    seed = _decode_seed(env) if env else _load_or_create_seed()
    return ed25519.Ed25519PrivateKey.from_private_bytes(seed)


def public_key_hex(private_key=None) -> str:  # type: ignore[no-untyped-def]
    """Hex of the raw 32-byte public key (share this with verifiers)."""
    pk = private_key or resolve_private_key()
    return pk.public_key().public_bytes_raw().hex()


def key_id_from_public_hex(public_hex: str) -> str:
    import hashlib

    return hashlib.sha256(bytes.fromhex(public_hex)).hexdigest()[:12]


def sign(private_key, message: bytes) -> str:  # type: ignore[no-untyped-def]
    return private_key.sign(message).hex()


def verify(public_hex: str, message: bytes, signature_hex: str) -> bool:
    ed25519 = _load_cryptography()
    from cryptography.exceptions import InvalidSignature

    try:
        pub = ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_hex))
        pub.verify(bytes.fromhex(signature_hex), message)
        return True
    except (InvalidSignature, ValueError):
        return False
