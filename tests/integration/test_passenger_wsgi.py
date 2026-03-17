"""Integration checks for the Passenger WSGI entrypoint."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_passenger_wsgi_application_importable_in_isolated_python() -> None:
    """Ensure Passenger WSGI can initialize from a clean interpreter."""

    repo_root = Path(__file__).resolve().parents[2]
    passenger_path = repo_root / "src" / "greektax" / "backend" / "passenger_wsgi.py"

    script = f"""
from runpy import run_path

namespace = run_path({str(passenger_path)!r})
application = namespace.get('application')
assert application is not None, 'Expected application to be defined'
"""

    result = subprocess.run(
        [sys.executable, "-I", "-c", script],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, (
        "Expected passenger_wsgi application import to succeed in isolated mode. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
