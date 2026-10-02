"""Ensure the bundled frontend configuration matches the config API."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "build_client_config.py"


def test_client_config_module_is_current(capsys) -> None:
    """Year YAML, translation or version changes must ship a rebuilt module.

    If this fails, run ``python scripts/build_client_config.py`` and commit
    ``src/frontend/assets/scripts/data/client-config.generated.js``.
    """

    spec = importlib.util.spec_from_file_location("build_client_config", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    exit_code = module.main(["--check"])

    assert exit_code == 0, capsys.readouterr().out
