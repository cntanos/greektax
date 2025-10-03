"""Unit coverage for year configuration discovery and parsing utilities."""

from __future__ import annotations

from pathlib import Path
from shutil import copy2

import pytest

from greektax.backend.config import year_config


@pytest.fixture()
def isolated_config_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Return a temporary configuration directory patched into ``year_config``."""

    original_directory = year_config.CONFIG_DIRECTORY
    for filename in ("2024.yaml", "2025.yaml"):
        copy2(original_directory / filename, tmp_path / filename)

    monkeypatch.setattr(year_config, "CONFIG_DIRECTORY", tmp_path)
    year_config.load_year_configuration.cache_clear()

    yield tmp_path

    year_config.load_year_configuration.cache_clear()


def test_available_years_discovers_new_config_file(
    isolated_config_directory: Path,
) -> None:
    """The helper should surface any new ``*.yaml`` files without code changes."""

    new_year_path = isolated_config_directory / "2030.yaml"
    new_year_path.write_text((isolated_config_directory / "2025.yaml").read_text())

    years = year_config.available_years()

    assert years == (2024, 2025, 2030)


def test_available_years_ignores_non_numeric_filenames(
    isolated_config_directory: Path,
) -> None:
    """Non-numeric filenames should be ignored to avoid unexpected crashes."""

    (isolated_config_directory / "legacy.yaml").write_text("meta: {}\n")
    (isolated_config_directory / "2025.backup").write_text("meta: {}\n")

    years = year_config.available_years()

    assert years == (2024, 2025)
