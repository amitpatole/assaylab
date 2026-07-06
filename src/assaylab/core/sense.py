"""The ``Assay`` sense — satisfies the agentsensory ``Sense`` protocol."""

from __future__ import annotations

from ..config import Settings
from ..models import Report
from .analyze import analyze


class Assay:
    """Validation-intelligence sense: grade a test/CI source into a Report."""

    name = "assaylab"

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()

    def available(self) -> bool:
        return True

    async def analyze(self, source: str, **kwargs: object) -> Report:
        backend = kwargs.get("backend")
        baseline = kwargs.get("baseline")
        return await analyze(
            source,
            backend=backend if isinstance(backend, str) else None,
            baseline=baseline if isinstance(baseline, str) else None,
            settings=self.settings,
        )
