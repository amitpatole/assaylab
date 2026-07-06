"""Ollama provider (behind the ``llm`` extra) — local or hosted.

Talks to an Ollama-compatible ``/api/generate`` endpoint. Base URL from
``ASSAYLAB_OLLAMA_URL`` (default local ``http://127.0.0.1:11434``); an optional
bearer token is read from ``~/.config/ollama/key`` for hosted inference. The
token is never logged. Calls are timeout-bounded.
"""

from __future__ import annotations

import os
from pathlib import Path

from ..provider import MissingDependencyError, _cap

_DEFAULT_URL = "http://127.0.0.1:11434"
_DEFAULT_MODEL = "llama3.1"
_TIMEOUT_S = 120.0


class OllamaProvider:
    name = "ollama"

    def __init__(self, model: str | None = None, base_url: str | None = None) -> None:
        self.model = model or os.environ.get("ASSAYLAB_OLLAMA_MODEL", _DEFAULT_MODEL)
        self.base_url = (base_url or os.environ.get("ASSAYLAB_OLLAMA_URL", _DEFAULT_URL)).rstrip("/")

    def _token(self) -> str | None:
        key = Path.home() / ".config" / "ollama" / "key"
        if key.is_file():
            tok = key.read_text(encoding="utf-8").strip()
            return tok or None
        return None

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

        headers = {}
        token = self._token()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system or "You are a careful software test engineer.",
            "stream": False,
            "options": {"num_predict": max_tokens},
        }
        resp = httpx.post(f"{self.base_url}/api/generate", json=payload,
                          headers=headers, timeout=_TIMEOUT_S)
        resp.raise_for_status()
        return _cap(str(resp.json().get("response", "")))
