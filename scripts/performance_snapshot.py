#!/usr/bin/env python3
"""Collect baseline performance and accessibility metrics for GreekTax."""

from __future__ import annotations

import json
import os
import sys
from html.parser import HTMLParser
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from greektax.backend.app.services.calculation_service import calculate_tax  # noqa: E402

SAMPLE_PAYLOAD = {
    "year": 2024,
    "locale": "en",
    "dependents": {"children": 1},
    "employment": {"gross_income": 32000, "payments_per_year": 14},
    "freelance": {
        "profit": 12000,
        "mandatory_contributions": 1800,
        "auxiliary_contributions": 300,
    },
    "rental": {"gross_income": 7200, "deductible_expenses": 1200},
    "investment": {"dividends": 1500, "interest": 450},
    "obligations": {"vat": 600, "enfia": 320},
    "deductions": {"donations": 200, "medical": 350},
}


class AccessibilityScanner(HTMLParser):
    """Simple scanner that counts ARIA usage for baseline reporting."""

    def __init__(self) -> None:
        super().__init__()
        self.nodes_with_aria = 0
        self.roles: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:  # noqa: D401
        attributes = dict(attrs)
        if any(name.startswith("aria-") for name in attributes):
            self.nodes_with_aria += 1
        role = attributes.get("role")
        if role:
            self.roles.add(role)


def measure_backend(iterations: int) -> dict[str, float]:
    """Return timing statistics for repeated backend calculations."""

    payload = dict(SAMPLE_PAYLOAD)
    calculate_tax(payload)  # Warm cache
    start = perf_counter()
    for _ in range(iterations):
        calculate_tax(payload)
    elapsed = perf_counter() - start
    return {
        "iterations": iterations,
        "total_ms": elapsed * 1000,
        "average_ms": (elapsed / iterations) * 1000,
    }


def bundle_sizes() -> dict[str, int]:
    """Return file size information for critical front-end assets."""

    assets = {}
    for relative in (
        "src/frontend/assets/scripts/main.js",
        "src/frontend/assets/styles/main.css",
    ):
        path = ROOT / relative
        if path.exists():
            assets[relative] = path.stat().st_size
    return assets


def accessibility_snapshot() -> dict[str, object]:
    """Report the number of elements carrying ARIA attributes and roles."""

    html_path = ROOT / "src" / "frontend" / "index.html"
    parser = AccessibilityScanner()
    parser.feed(html_path.read_text(encoding="utf-8"))
    return {
        "nodes_with_aria": parser.nodes_with_aria,
        "roles": sorted(parser.roles),
    }


def main() -> None:
    iterations = int(os.getenv("GREEKTAX_PROFILE_ITERATIONS", "75"))
    report = {
        "backend": measure_backend(iterations),
        "frontend_assets_bytes": bundle_sizes(),
        "accessibility_snapshot": accessibility_snapshot(),
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
