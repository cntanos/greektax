"""Integration tests for the tax calculation REST endpoint."""

from __future__ import annotations

import json
from http import HTTPStatus
from pathlib import Path
from typing import Dict, Iterable

import pytest
from flask.testing import FlaskClient

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "regression_scenarios.json"


def _load_scenarios() -> Iterable[Dict[str, object]]:
    with DATA_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


@pytest.mark.parametrize("scenario", _load_scenarios(), ids=lambda item: item["name"])
def test_calculation_endpoint_matches_regression_scenarios(
    client: FlaskClient, scenario: Dict[str, object]
) -> None:
    """Each regression scenario should remain stable over time."""

    response = client.post("/api/v1/calculations", json=scenario["payload"])
    assert response.status_code == HTTPStatus.OK

    result = response.get_json()
    expected = scenario["expectations"]

    summary = result["summary"]
    for key, value in expected["summary"].items():
        assert summary[key] == pytest.approx(value)

    details = {item["category"]: item for item in result["details"]}
    for category, expectations in expected["details"].items():
        assert category in details, f"Missing detail for {category}"
        for field, value in expectations.items():
            assert details[category][field] == pytest.approx(value)


def test_calculation_endpoint_uses_accept_language_header(client: FlaskClient) -> None:
    """Accept-Language header should influence locale if body omits it."""

    response = client.post(
        "/api/v1/calculations",
        json={"year": 2024, "employment": {"gross_income": 10_000}},
        headers={"Accept-Language": "el"},
    )

    assert response.status_code == HTTPStatus.OK
    payload = response.get_json()
    assert payload["meta"]["locale"] == "el"
    assert payload["summary"]["labels"]["income_total"] == "Συνολικό εισόδημα"


def test_calculation_endpoint_returns_validation_error(client: FlaskClient) -> None:
    """Invalid payloads should return a structured 400 response."""

    response = client.post(
        "/api/v1/calculations",
        data="not-json",
        content_type="text/plain",
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    payload = response.get_json()
    assert payload["error"] == "bad_request"
    assert "JSON" in payload["message"].upper()


def test_calculation_endpoint_handles_service_errors(client: FlaskClient) -> None:
    """Domain validation errors should surface as 400 responses."""

    response = client.post(
        "/api/v1/calculations",
        json={"year": 2024, "employment": {"gross_income": -1}},
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    payload = response.get_json()
    assert payload["error"] == "validation_error"
    assert "cannot be negative" in payload["message"].lower()


def test_calculation_endpoint_accepts_mixed_employment_inputs(client: FlaskClient) -> None:
    """Submitting both annual and monthly salary amounts remains stable."""

    payload = {
        "year": 2024,
        "employment": {
            "gross_income": 30_000,
            "monthly_income": 1_500,
            "payments_per_year": 14,
        },
    }

    response = client.post("/api/v1/calculations", json=payload)
    assert response.status_code == HTTPStatus.OK

    result = response.get_json()
    summary = result["summary"]
    assert summary["income_total"] == pytest.approx(30_000.0)
    assert summary["taxable_income"] == pytest.approx(30_000.0)

    employment_detail = next(
        item for item in result["details"] if item["category"] == "employment"
    )
    assert employment_detail["gross_income"] == pytest.approx(30_000.0)
    assert employment_detail["monthly_gross_income"] == pytest.approx(1_500.0)
    assert employment_detail["gross_income_per_payment"] == pytest.approx(
        30_000 / 14, abs=0.01
    )


def test_calculation_endpoint_handles_employment_and_pension_toggles(
    client: FlaskClient,
) -> None:
    """Employment and pension sections can be combined without conflicts."""

    payload = {
        "year": 2024,
        "employment": {"gross_income": 18_000},
        "pension": {"gross_income": 9_000},
    }

    response = client.post("/api/v1/calculations", json=payload)
    assert response.status_code == HTTPStatus.OK

    result = response.get_json()
    categories = {detail["category"] for detail in result["details"]}
    assert {"employment", "pension"}.issubset(categories)

    employment_detail = next(
        item for item in result["details"] if item["category"] == "employment"
    )
    pension_detail = next(
        item for item in result["details"] if item["category"] == "pension"
    )

    assert employment_detail["gross_income"] == pytest.approx(18_000.0)
    assert pension_detail["gross_income"] == pytest.approx(9_000.0)
