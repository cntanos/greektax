"""Regression coverage ensuring calculator outputs stay stable."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from greektax.backend.app.services.calculation_service import calculate_tax

_DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "regression_scenarios.json"


@pytest.mark.parametrize(
    "scenario",
    json.loads(_DATA_PATH.read_text("utf-8")),
    ids=lambda item: f"{item['name']}_{item['payload']['year']}",
)
def test_calculate_tax_matches_regression_scenario(scenario: dict[str, object]) -> None:
    """The calculation service returns the expected results for known payloads."""

    payload = scenario["payload"]
    expectations = scenario["expectations"]

    result = calculate_tax(payload)

    summary = result["summary"]
    for key, value in expectations["summary"].items():
        assert summary[key] == pytest.approx(value)

    details = {item["category"]: item for item in result["details"]}
    for category, detail_expectations in expectations["details"].items():
        assert category in details, f"Missing detail for {category}"
        for field, value in detail_expectations.items():
            assert details[category][field] == pytest.approx(value)
