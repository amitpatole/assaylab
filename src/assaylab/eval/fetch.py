"""Fetch public eval corpora (the ``datasets`` extra). CC BY 4.0 sources."""

from __future__ import annotations

from pathlib import Path

from platformdirs import user_cache_dir

from ..errors import MissingDependencyError

# FlakeFlagger (Zenodo 4450723) — only the small summary CSVs (a few MB each),
# never the multi-GB raw-log .tgz archives.
_FLAKEFLAGGER = "https://zenodo.org/records/4450723/files/{name}?download=1"
_FF_FILES = ("test_results.csv", "test_features.csv", "Project_Info.csv")
_MAX_BYTES = 64 * 1024 * 1024  # summary CSVs are well under this


def _cache_dir() -> Path:
    d = Path(user_cache_dir("assaylab")) / "flakeflagger"
    d.mkdir(parents=True, exist_ok=True)
    return d


def fetch_flakeflagger() -> dict[str, Path]:
    """Download the FlakeFlagger summary CSVs to the cache; return their paths."""
    try:
        import httpx
    except ImportError as e:
        raise MissingDependencyError(
            "fetching eval data needs httpx; pip install assaylab[datasets]"
        ) from e

    out: dict[str, Path] = {}
    dest = _cache_dir()
    for name in _FF_FILES:
        path = dest / name
        if not path.is_file():
            with httpx.stream("GET", _FLAKEFLAGGER.format(name=name),
                              follow_redirects=True, timeout=120) as r:
                r.raise_for_status()
                buf = bytearray()
                for chunk in r.iter_bytes():
                    buf.extend(chunk)
                    if len(buf) > _MAX_BYTES:
                        raise MissingDependencyError(f"{name} unexpectedly large — aborting")
                path.write_bytes(buf)
        out[name] = path
    return out
