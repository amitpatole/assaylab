"""assaylab CLI (Typer). Entry point: ``assaylab``.

Commands grade CI/test sources into pass/warn/fail, cluster failures into
signatures, and hand off to a brain. ``check`` exits non-zero on FAIL so it
drops straight into a CI gate.
"""

from __future__ import annotations

import asyncio
import json

import typer

from .. import __version__
from ..config import Settings
from ..core import analyze as _analyze
from ..core import ingest as _ingest
from ..core import perceive as _perceive
from ..core import signature as _sig
from ..models import Report
from .doctor import run_checks

app = typer.Typer(
    name="assaylab",
    help="Validation intelligence for CI — cluster failures into signatures, grade pass/warn/fail, "
    "and hand off to a brain. Contract-compatible with agentsensory.",
    no_args_is_help=True,
    add_completion=False,
)


def _print_report(report: Report) -> None:
    typer.echo(f"verdict: {report.verdict.value.upper()}  —  {report.summary}")
    for i in report.issues:
        det = i.detail
        tests = det.get("tests", [])
        typer.echo(f"  [{i.severity.value}] {i.kind}: {i.message}")
        if tests:
            typer.echo(f"      tests: {', '.join(tests[:5])}" + (" …" if len(tests) > 5 else ""))
        if det.get("signature_id"):
            typer.echo(f"      signature: {det['signature_id']}  files: {', '.join(det.get('files', [])[:3])}")


@app.command()
def version() -> None:
    """Print the assaylab version."""
    typer.echo(__version__)


@app.command()
def doctor() -> None:
    """Check the install: contract, safe XML, backends, optional extras."""
    all_ok = True
    for c in run_checks():
        mark = "ok " if c.ok else "MISS"
        if not c.ok and c.name in ("agentsensory contract", "safe XML (defusedxml)"):
            all_ok = False
        typer.echo(f"[{mark}] {c.name}: {c.detail}")
    raise typer.Exit(code=0 if all_ok else 1)


@app.command()
def check(
    source: str = typer.Argument(..., help="Path to (or inline) JUnit XML / outcome CSV-JSON."),
    backend: str | None = typer.Option(None, "--backend", "-b", help="junit | jsonl (inferred if omitted)."),
    baseline: str | None = typer.Option(None, "--baseline", help="Prior results; signatures absent here are flagged NEW."),
    as_json: bool = typer.Option(False, "--json", help="Emit the full Report as JSON."),
) -> None:
    """Grade a test source. Exits non-zero on FAIL (CI gate)."""
    report = asyncio.run(_analyze(source, backend=backend, baseline=baseline, settings=Settings()))
    if as_json:
        typer.echo(json.dumps(report.model_dump(mode="json"), indent=2))
    else:
        _print_report(report)
    raise typer.Exit(code=1 if report.verdict.value == "fail" else 0)


@app.command()
def signatures(
    source: str = typer.Argument(..., help="Path to (or inline) JUnit XML / outcome CSV-JSON."),
    backend: str | None = typer.Option(None, "--backend", "-b"),
) -> None:
    """List failure signatures in a source, most frequent first."""
    records = _ingest(source, backend=backend, settings=Settings())
    sigs = _sig.cluster(records)
    if not sigs:
        typer.echo("no failure signatures.")
        raise typer.Exit(code=0)
    for s in sigs:
        typer.echo(f"{s.signature_id}  x{s.count}  {s.exception_type or '(no type)'}  "
                   f"[{len(s.tests)} test(s)]  {s.sample_message[:80]}")


@app.command()
def perceive(
    source: str = typer.Argument(..., help="Path to (or inline) JUnit XML / outcome CSV-JSON."),
    backend: str | None = typer.Option(None, "--backend", "-b"),
    baseline: str | None = typer.Option(None, "--baseline"),
) -> None:
    """Emit the brain-facing Handoff (JSON) for a source."""
    handoff = asyncio.run(_perceive(source, backend=backend, baseline=baseline, settings=Settings()))
    typer.echo(json.dumps(handoff.model_dump(mode="json"), indent=2))


@app.command()
def demo() -> None:
    """Grade a synthetic broken suite (FAIL) then its fix (PASS). No API key, no network."""
    from ._demo_assets import broken_suite, fixed_suite

    typer.echo("assaylab demo — a synthetic suite graded, then its fix (no API key, no network)\n")

    typer.echo("1) broken suite:")
    before = asyncio.run(_analyze(broken_suite(), backend="junit", settings=Settings()))
    _print_report(before)

    typer.echo("\n2) after the fix:")
    after = asyncio.run(_analyze(fixed_suite(), backend="junit", settings=Settings()))
    _print_report(after)

    ok = before.verdict.value == "fail" and after.verdict.value == "pass" and len(before.issues) == 2
    typer.echo("\n" + (
        "demo OK: 3 failures -> 2 signatures -> FAIL, then fixed -> PASS"
        if ok else "demo did not behave as expected"
    ))
    raise typer.Exit(code=0 if ok else 1)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
