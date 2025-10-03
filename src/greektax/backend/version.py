"""Utilities for exposing the project version consistently."""

from __future__ import annotations

from functools import lru_cache
from importlib import metadata
from pathlib import Path
from typing import Final

PACKAGE_NAME: Final = "greektax"


@lru_cache(maxsize=1)
def get_project_version() -> str:
    """Return the packaged version, falling back to ``pyproject.toml`` when needed."""

    try:
        return metadata.version(PACKAGE_NAME)
    except metadata.PackageNotFoundError:
        return _read_version_from_pyproject()


def _read_version_from_pyproject() -> str:
    """Parse ``pyproject.toml`` for the version value.

    The project metadata acts as the canonical source when package metadata is
    unavailable (such as editable installs during development or tests).
    """

    pyproject_path = Path(__file__).resolve().parents[3] / "pyproject.toml"
    if not pyproject_path.exists():  # pragma: no cover - repository invariant
        msg = f"Unable to locate project metadata at {pyproject_path}"  # pragma: no cover
        raise RuntimeError(msg)  # pragma: no cover

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
            if not version:
                break
            return version

    msg = "Unable to determine project version from pyproject.toml"
    raise RuntimeError(msg)


__all__ = ["get_project_version"]
