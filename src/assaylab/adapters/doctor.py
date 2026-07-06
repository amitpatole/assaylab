"""``assaylab doctor`` — verify the install without importing heavy extras."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.util import find_spec

from ..config import Settings

# (label, module, hint) — presence probed via find_spec, never imported.
_OPTIONAL = [
    ("dataset fetch", "httpx", "pip install assaylab[datasets]"),
    ("LLM (claude)", "anthropic", "pip install assaylab[llm]"),
    ("REST service", "fastapi", "pip install assaylab[serve]"),
    ("MCP server", "mcp", "pip install assaylab[mcp]"),
]

# Checks whose failure makes `doctor` exit non-zero.
_REQUIRED = {"agentsensory contract", "safe XML (defusedxml)"}


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


def _has(mod: str) -> bool:
    try:
        return find_spec(mod) is not None
    except (ImportError, ValueError):
        return False


def run_checks(settings: Settings | None = None) -> list[Check]:
    settings = settings or Settings()
    checks: list[Check] = []

    try:
        import agentsensory

        checks.append(Check("agentsensory contract", True, f"v{agentsensory.__version__}"))
    except Exception as e:  # noqa: BLE001
        checks.append(Check("agentsensory contract", False, str(e)))

    checks.append(Check("safe XML (defusedxml)", _has("defusedxml"),
                        "installed" if _has("defusedxml") else "MISSING — XML parsing unsafe"))
    checks.append(Check("junit backend", True, "JUnit/xUnit XML (built-in)"))
    checks.append(Check("jsonl backend", True, "CSV/JSON/JSONL outcomes (built-in)"))

    for label, mod, hint in _OPTIONAL:
        present = _has(mod)
        checks.append(Check(label, present, "installed" if present else f"not installed — {hint}"))

    checks.append(Check(
        "REST auth token",
        True,
        "set (auth enabled)" if settings.api_token else "unset (loopback-only; required off-loopback)",
    ))
    return checks
