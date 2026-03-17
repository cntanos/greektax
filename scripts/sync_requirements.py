#!/usr/bin/env python3
"""Synchronize requirements files from pyproject.toml metadata."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT_PATH = ROOT / "pyproject.toml"

REQUIREMENTS_PATH = ROOT / "requirements.txt"
REQUIREMENTS_DEV_PATH = ROOT / "requirements-dev.txt"
BACKEND_REQUIREMENTS_PATH = ROOT / "src/greektax/backend/requirements.txt"


def _load_pyproject() -> dict:
    with PYPROJECT_PATH.open("rb") as pyproject_file:
        return tomllib.load(pyproject_file)


def _render_runtime_requirements(runtime_dependencies: list[str]) -> str:
    return "\n".join(runtime_dependencies) + "\n"


def _render_dev_requirements(dev_dependencies: list[str]) -> str:
    lines = ["-r requirements.txt", *dev_dependencies]
    return "\n".join(lines) + "\n"


def build_expected_requirements() -> dict[Path, str]:
    pyproject = _load_pyproject()
    project = pyproject["project"]
    runtime_dependencies = project.get("dependencies", [])
    optional_dependencies = project.get("optional-dependencies", {})
    dev_dependencies = optional_dependencies.get("dev", [])

    runtime_content = _render_runtime_requirements(runtime_dependencies)

    return {
        REQUIREMENTS_PATH: runtime_content,
        BACKEND_REQUIREMENTS_PATH: runtime_content,
        REQUIREMENTS_DEV_PATH: _render_dev_requirements(dev_dependencies),
    }


def check_drift(expected_by_path: dict[Path, str]) -> list[Path]:
    drifted_paths: list[Path] = []
    for path, expected_content in expected_by_path.items():
        if not path.exists() or path.read_text(encoding="utf-8") != expected_content:
            drifted_paths.append(path)
    return drifted_paths


def write_files(expected_by_path: dict[Path, str]) -> None:
    for path, content in expected_by_path.items():
        path.write_text(content, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync requirements files from pyproject.toml dependencies."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail with a non-zero exit code if files are out of sync.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    expected_by_path = build_expected_requirements()

    if args.check:
        drifted_paths = check_drift(expected_by_path)
        if drifted_paths:
            print("Requirements drift detected. Regenerate with:")
            print("  python scripts/sync_requirements.py")
            for path in drifted_paths:
                print(f"- {path.relative_to(ROOT)}")
            return 1

        print("Requirements files are in sync with pyproject.toml.")
        return 0

    write_files(expected_by_path)
    print("Updated requirements files from pyproject.toml metadata.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
