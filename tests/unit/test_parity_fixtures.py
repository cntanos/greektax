"""Ensure the committed calculation parity fixtures match the engine."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "generate_parity_fixtures.py"


def test_parity_fixtures_are_current(capsys) -> None:
    """Behaviour changes must come with regenerated, reviewed fixtures.

    If this fails, run ``python scripts/generate_parity_fixtures.py`` and
    check that every changed expectation in ``tests/data/parity`` is intended.
    """

    spec = importlib.util.spec_from_file_location("generate_parity_fixtures", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    exit_code = module.main(["--check"])

    assert exit_code == 0, capsys.readouterr().out
