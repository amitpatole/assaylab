"""Backend resolution: built-ins fast-path, then third-party entry points."""

from __future__ import annotations

from collections.abc import Callable
from importlib.metadata import entry_points
from pathlib import Path
from typing import cast

from ..config import Settings
from ..errors import ConfigError
from .base import ResultsBackend
from .jsonl import JsonlBackend
from .junit import JUnitBackend

_ENTRY_GROUP = "assaylab.backends"
_BUILTINS: dict[str, Callable[[], ResultsBackend]] = {
    "junit": JUnitBackend,
    "jsonl": JsonlBackend,
}


def resolve_backend(name: str | None = None, settings: Settings | None = None) -> ResultsBackend:
    """Return the requested backend, defaulting to ``settings.backend``."""
    settings = settings or Settings()
    name = (name or settings.backend or "junit").lower()

    builtin = _BUILTINS.get(name)
    if builtin is not None:
        return builtin()

    for ep in entry_points(group=_ENTRY_GROUP):
        if ep.name == name:
            factory = ep.load()
            backend = factory() if callable(factory) else factory
            return cast(ResultsBackend, backend)

    raise ConfigError(f"unknown backend {name!r}")


def infer_backend(source: str) -> str:
    """Guess a backend from a source path's extension (falls back to ``junit``)."""
    suffix = Path(source).suffix.lower()
    if suffix == ".xml":
        return "junit"
    if suffix in (".json", ".jsonl", ".ndjson", ".csv"):
        return "jsonl"
    # Inline content: sniff the first non-space char.
    head = source.lstrip()[:1]
    if head == "<":
        return "junit"
    if head in ("[", "{"):
        return "jsonl"
    return "junit"
