"""Attestation: signed, verifiable selection receipts (HMAC-SHA256, no default key)."""

from __future__ import annotations

from .keys import key_id, resolve_key
from .receipt import SCHEMA, Receipt, hash_ids

__all__ = ["Receipt", "SCHEMA", "hash_ids", "resolve_key", "key_id"]
