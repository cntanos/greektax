#!/usr/bin/env python3
"""Enforce frontend bundle size budgets for critical assets."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

BUDGETS = {
    Path("src/frontend/assets/scripts/main.js"): 2_048,
    Path("src/frontend/assets/styles/main.css"): 60_000,
}


def main() -> int:
    over_budget = []

    for relative_path, max_bytes in BUDGETS.items():
        absolute_path = ROOT / relative_path
        size = absolute_path.stat().st_size
        if size > max_bytes:
            over_budget.append((relative_path, size, max_bytes))

    if over_budget:
        print("Bundle size budget exceeded:")
        for relative_path, size, max_bytes in over_budget:
            print(f"- {relative_path}: {size} bytes > {max_bytes} bytes")
        return 1

    print("Bundle size budgets are satisfied.")
    for relative_path, max_bytes in BUDGETS.items():
        size = (ROOT / relative_path).stat().st_size
        print(f"- {relative_path}: {size}/{max_bytes} bytes")

    return 0


if __name__ == "__main__":
    sys.exit(main())
