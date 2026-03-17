#!/usr/bin/env python3
"""Run the consolidated local quality gate."""

from __future__ import annotations

import subprocess
import sys

COMMANDS: list[list[str]] = [
    ["ruff", "check", "src", "tests"],
    ["mypy", "src"],
    ["vulture", "src", "tests", "--min-confidence", "100", "--ignore-names", "cls,__context,package"],
    ["pip-audit", "-r", "requirements.txt", "-r", "requirements-dev.txt"],
    ["python", "scripts/check_bundle_size.py"],
    ["node", "--test", "tests/frontend"],
]


def run_command(command: list[str]) -> int:
    print(f"\n$ {' '.join(command)}")
    completed = subprocess.run(command, check=False)
    return completed.returncode


def main() -> int:
    for command in COMMANDS:
        return_code = run_command(command)
        if return_code != 0:
            print(f"\nQuality command failed: {' '.join(command)}")
            return return_code

    print("\nQuality command completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
