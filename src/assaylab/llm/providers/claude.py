"""Anthropic Claude provider (behind the ``llm`` extra).

Uses the official ``anthropic`` SDK. The API key resolves from the environment
(``ANTHROPIC_API_KEY``) — never hardcoded, never logged. Defaults to the most
capable model; override via ``ASSAYLAB_CLAUDE_MODEL``.
"""

from __future__ import annotations

import os

from ..provider import MissingDependencyError, _cap

_DEFAULT_MODEL = "claude-opus-4-8"


class ClaudeProvider:
    name = "claude"

    def __init__(self, model: str | None = None) -> None:
        self.model = model or os.environ.get("ASSAYLAB_CLAUDE_MODEL", _DEFAULT_MODEL)

    def available(self) -> bool:
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False
        return bool(os.environ.get("ANTHROPIC_API_KEY"))

    def complete(self, prompt: str, *, system: str = "", max_tokens: int = 4096) -> str:
        try:
            import anthropic
        except ImportError as e:
            raise MissingDependencyError(
                "the claude provider needs the anthropic SDK; pip install assaylab[llm]"
            ) from e

        client = anthropic.Anthropic()  # key resolved from env by the SDK
        resp = client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system or "You are a careful software test engineer.",
            messages=[{"role": "user", "content": prompt}],
        )
        # Safety classifiers may decline — check before reading content.
        if getattr(resp, "stop_reason", None) == "refusal":
            return "# provider refused this request"
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
        return _cap(text)
