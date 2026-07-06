"""assaylab exceptions.

Only ``UnsafeSourceError`` text is safe to surface to a remote caller (it names
a rejected-input reason, never internals). Everything else is sanitized at the
REST boundary.
"""

from __future__ import annotations


class AssaylabError(Exception):
    """Base for all assaylab errors."""


class ConfigError(AssaylabError):
    """Invalid configuration or unknown backend."""


class SourceError(AssaylabError):
    """A source could not be read or parsed into test records."""


class UnsafeSourceError(SourceError):
    """A source was rejected by an input guard (size cap, malformed, unsafe path/XML).

    The message is caller-safe: it states *why* the input was refused without
    leaking filesystem paths or stack internals.
    """


class MissingDependencyError(AssaylabError):
    """An optional extra is required but not installed."""
