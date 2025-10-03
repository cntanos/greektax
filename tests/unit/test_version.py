"""Unit coverage for the project version helper."""

from __future__ import annotations

from importlib import metadata
from pathlib import Path

from greektax.backend.version import get_project_version


def read_pyproject_version() -> str:
    pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
    current_section: str | None = None
    for raw_line in pyproject_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            current_section = line.strip("[]")
            continue
        if current_section == "project" and line.startswith("version"):
            _, _, value = line.partition("=")
            version = value.strip().strip('"')
            if version:
                return version
    raise RuntimeError("Version not found in pyproject.toml")


def test_get_project_version_matches_pyproject(monkeypatch) -> None:
    get_project_version.cache_clear()  # type: ignore[attr-defined]
    expected = read_pyproject_version()

    monkeypatch.setattr(metadata, "version", lambda package: expected)

    assert get_project_version() == expected


def test_get_project_version_falls_back_to_pyproject(monkeypatch) -> None:
    get_project_version.cache_clear()  # type: ignore[attr-defined]
    expected = read_pyproject_version()

    def raise_package_not_found(_: str) -> str:
        raise metadata.PackageNotFoundError

    monkeypatch.setattr(metadata, "version", raise_package_not_found)

    assert get_project_version() == expected
