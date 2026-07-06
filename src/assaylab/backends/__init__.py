"""Ingestion backends: read a source into normalized :class:`TestRecord`s."""

from __future__ import annotations

from .base import ResultsBackend, read_source
from .registry import infer_backend, resolve_backend

__all__ = ["ResultsBackend", "read_source", "resolve_backend", "infer_backend"]
