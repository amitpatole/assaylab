"""Ollama provider (behind the ``llm`` extra) — local or hosted.

Talks to an Ollama-compatible ``/api/generate`` endpoint. Base URL from
``ASSAYLAB_OLLAMA_URL`` (default local ``http://127.0.0.1:11434``); an optional
bearer token is read from ``~/.config/ollama/key`` for hosted inference.

Security: the token is attached **only** to a loopback host, or to an ``https``
host when ``ASSAYLAB_OLLAMA_ALLOW_REMOTE_TOKEN=1`` is explicitly set — otherwise
we refuse rather than leak the credential to an arbitrary/SSRF target. The token
file is read without following symlinks and is size-capped. The response body is
read with a hard byte cap so a hostile endpoint can't exhaust memory.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path
from urllib.parse import urlparse

from ...errors import ConfigError, UnsafeSourceError
from ..provider import MissingDependencyError, _cap

_DEFAULT_URL = "http://127.0.0.1:11434"
_DEFAULT_MODEL = "llama3.1"
_TIMEOUT_S = 120.0
_MAX_RESPONSE_BYTES = 8 * 1024 * 1024
_LOOPBACK = {"127.0.0.1", "localhost", "::1", "[::1]"}


class OllamaProvider:
    name = "ollama"

    def __init__(self, model: str | None = None, base_url: str | None = None) -> None:
        self.model = model or os.environ.get("ASSAYLAB_OLLAMA_MODEL", _DEFAULT_MODEL)
        self.base_url = (base_url or os.environ.get("ASSAYLAB_OLLAMA_URL", _DEFAULT_URL)).rstrip("/")

    def _token(self) -> str | None:
        key = Path.home() / ".config" / "ollama" / "key"
        try:
            fd = os.open(str(key), os.O_RDONLY | os.O_NOFOLLOW)
        except FileNotFoundError:
            return None
        except OSError as e:
            raise UnsafeSourceError("ollama key is a symlink or unreadable — refusing") from e
        try:
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode) or st.st_size > 4096:
                raise UnsafeSourceError("ollama key is not a plausible key file — refusing")
            tok = os.read(fd, 4096).decode("utf-8", "replace").strip()
            return tok or None
        finally:
            os.close(fd)

    def _auth_header(self) -> dict[str, str]:
        """Attach the bearer token only to a trusted host; otherwise fail closed."""
        token = self._token()
        if token is None:
            return {}
        parsed = urlparse(self.base_url)
        host = (parsed.hostname or "").lower()
        if host in _LOOPBACK:
            return {"Authorization": f"Bearer {token}"}
        if parsed.scheme == "https" and os.environ.get("ASSAYLAB_OLLAMA_ALLOW_REMOTE_TOKEN") == "1":
            return {"Authorization": f"Bearer {token}"}
        raise ConfigError(
            f"refusing to send the ollama token to {self.base_url!r}: only loopback, or an https "
            f"host with ASSAYLAB_OLLAMA_ALLOW_REMOTE_TOKEN=1, may receive the credential"
        )

    def available(self) -> bool:
        try:
            import httpx  # noqa: F401
        except ImportError:
            return False
        return True

    def complete(self, prompt: str, *, system: str = "", max_tokens: int = 4096) -> str:
        try:
            import httpx
        except ImportError as e:
            raise MissingDependencyError(
                "the ollama provider needs httpx; pip install assaylab[llm]"
            ) from e

        headers = self._auth_header()
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system or "You are a careful software test engineer.",
            "stream": False,
            "options": {"num_predict": max_tokens},
        }
        # Stream the body and stop at a hard byte cap so a hostile/misbehaving
        # endpoint that ignores num_predict cannot exhaust memory.
        import json as _json

        with httpx.stream("POST", f"{self.base_url}/api/generate", json=payload,
                          headers=headers, timeout=_TIMEOUT_S) as resp:
            resp.raise_for_status()
            buf = bytearray()
            for chunk in resp.iter_bytes():
                buf.extend(chunk)
                if len(buf) > _MAX_RESPONSE_BYTES:
                    raise UnsafeSourceError("ollama response exceeded the size cap")
        try:
            data = _json.loads(buf.decode("utf-8", "replace"))
        except _json.JSONDecodeError as e:
            raise UnsafeSourceError(f"ollama returned malformed JSON: {e}") from None
        return _cap(str(data.get("response", "")))
