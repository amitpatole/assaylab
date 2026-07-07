from importlib.metadata import version

import assaylab


def test_version() -> None:
    assert assaylab.__version__ == "0.3.0"


def test_version_matches_package_metadata() -> None:
    # Drift guard: the installed distribution's version must equal __version__,
    # so pyproject and the module string can never disagree in a release.
    assert version("assaylab") == assaylab.__version__
