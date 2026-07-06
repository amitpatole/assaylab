"""LLM provider abstraction.

A provider only turns a prompt into text. It never executes anything. The
default ``template`` provider is fully deterministic and needs no API key, so
demos, tests, and CI run key-free; ``claude`` and ``ollama`` live behind the
``llm`` extra and are imported lazily.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..errors import ConfigError, MissingDependencyError

# Hard cap on any provider's returned text — bounds an over-long/hostile response.
MAX_COMPLETION_CHARS = 200_000


@runtime_checkable
class LLMProvider(Protocol):
    name: str

    def available(self) -> bool:
        """True when the provider can run (deps present / key resolvable)."""
        ...

    def complete(self, prompt: str, *, system: str = "", max_tokens: int = 4096) -> str:
        """Return a completion for ``prompt``. Output is caller-capped."""
        ...


def _cap(text: str) -> str:
    return text if len(text) <= MAX_COMPLETION_CHARS else text[:MAX_COMPLETION_CHARS]


def resolve_provider(name: str | None = None) -> LLMProvider:
    """Return a provider by name. Defaults to the key-free ``template`` provider."""
    name = (name or "template").lower()
    if name == "template":
        from .providers.template import TemplateProvider

        return TemplateProvider()
    if name in ("claude", "anthropic"):
        from .providers.claude import ClaudeProvider

        return ClaudeProvider()
    if name == "ollama":
        from .providers.ollama import OllamaProvider

        return OllamaProvider()
    raise ConfigError(f"unknown LLM provider {name!r}")


__all__ = ["LLMProvider", "resolve_provider", "MAX_COMPLETION_CHARS",
           "MissingDependencyError", "_cap"]
