"""Runtime settings, resolved from environment (``ASSAYLAB_*``).

Secrets (the receipt-signing key, the REST API token) are read from the
environment or a persisted per-installation file — never hardcoded. See
``assaylab.attest`` for key resolution (added in P3).
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

# Hard caps on attacker-controlled input, applied before allocation.
DEFAULT_MAX_SOURCE_BYTES = 64 * 1024 * 1024  # 64 MiB per source file
DEFAULT_MAX_RECORDS = 2_000_000  # per ingest call


class Settings(BaseSettings):
    """assaylab configuration.

    Every field is overridable via an ``ASSAYLAB_``-prefixed environment
    variable (e.g. ``ASSAYLAB_BACKEND=junit``).
    """

    model_config = SettingsConfigDict(env_prefix="ASSAYLAB_", extra="ignore")

    #: Default ingestion backend when a source's type is not inferred.
    backend: str = "junit"

    #: Bearer token required for non-loopback REST binds (unset = loopback only).
    api_token: str | None = None

    #: Bind host for the REST service; a routable bind requires ``api_token``.
    host: str = "127.0.0.1"
    port: int = 8000

    #: Resource caps for untrusted input.
    max_source_bytes: int = DEFAULT_MAX_SOURCE_BYTES
    max_records: int = DEFAULT_MAX_RECORDS
