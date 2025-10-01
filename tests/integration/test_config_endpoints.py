"""Integration coverage for configuration metadata endpoints."""

from http import HTTPStatus

from flask.testing import FlaskClient


def test_list_years_endpoint(client: FlaskClient) -> None:
    response = client.get("/api/v1/config/years")

    assert response.status_code == HTTPStatus.OK
    payload = response.get_json()
    years = payload["years"]
    assert any(entry["year"] == 2024 for entry in years)
    assert any(entry["year"] == 2025 for entry in years)
    assert payload["default_year"] == 2025


def test_investment_categories_endpoint(client: FlaskClient) -> None:
    response = client.get("/api/v1/config/2024/investment-categories?locale=el")

    assert response.status_code == HTTPStatus.OK
    payload = response.get_json()
    assert payload["locale"] == "el"
    categories = {item["id"]: item for item in payload["categories"]}
    assert "dividends" in categories
    assert categories["dividends"]["label"] == "Μερίσματα"


def test_investment_categories_missing_year(client: FlaskClient) -> None:
    response = client.get("/api/v1/config/1999/investment-categories")

    assert response.status_code == HTTPStatus.NOT_FOUND
    payload = response.get_json()
    assert payload["error"] == "not_found"


def test_deduction_hints_endpoint(client: FlaskClient) -> None:
    response = client.get("/api/v1/config/2024/deductions?locale=el")

    assert response.status_code == HTTPStatus.OK
    payload = response.get_json()
    assert payload["locale"] == "el"

    hints = {hint["id"]: hint for hint in payload["hints"]}
    assert "dependents.children" in hints
    children_hint = hints["dependents.children"]
    assert children_hint["input_id"] == "children-input"
    assert children_hint["description"].startswith("Επηρεάζει")
    assert children_hint["allowances"]
    tier_labels = {threshold["label"] for threshold in children_hint["allowances"][0]["thresholds"]}
    assert "3+ εξαρτώμενα τέκνα" in tier_labels
