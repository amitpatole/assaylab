"""Security regression: model loading is inert (JSON only, capped, schema-checked).

A pickled model is arbitrary-code-execution on load — a supply-chain hole if a
model is pulled from a registry/CI cache. assaylab persists and loads models as
JSON, so a hostile file can at worst be rejected, never executed. These tests
fail closed if someone reintroduces pickle or drops the guards.
"""

from __future__ import annotations

import pytest

from assaylab.errors import UnsafeSourceError
from assaylab.rca.service import load_model


def test_missing_model_file_refused(tmp_path) -> None:
    with pytest.raises(UnsafeSourceError):
        load_model(str(tmp_path / "nope.json"))


def test_oversized_model_refused(tmp_path) -> None:
    big = tmp_path / "big.json"
    big.write_text("0" * (5 * 1024 * 1024), encoding="utf-8")  # > 4 MiB cap
    with pytest.raises(UnsafeSourceError):
        load_model(str(big))


def test_wrong_schema_refused(tmp_path) -> None:
    p = tmp_path / "evil.json"
    p.write_text('{"schema": "attacker/1", "feature_names": [], "weights": [], "bias": 0}',
                 encoding="utf-8")
    with pytest.raises(ValueError):
        load_model(str(p))


def test_model_source_has_no_pickle() -> None:
    # A structural guard: the rca package must not import pickle for model I/O.
    from pathlib import Path

    import assaylab.rca.model as m

    src = Path(m.__file__).read_text(encoding="utf-8")
    # No pickle *usage* (the docstring may mention the word to explain why we avoid it).
    assert "import pickle" not in src
    assert "pickle.load" not in src
    assert "pickle.dump" not in src
    assert "import json" in src
