"""Integration coverage for configuration metadata endpoints."""

from http import HTTPStatus

from flask.testing import FlaskClient

from greektax.backend.version import get_project_version


def test_meta_endpoint(client: FlaskClient) -> None:
    response = client.get("/api/v1/config/meta")

    assert response.status_code == HTTPStatus.OK
    payload = response.get_json()
    assert payload == {"version": get_project_version()}


def test_list_years_endpoint(client: FlaskClient) -> None:
    response = client.get("/api/v1/config/years")

    assert response.status_code == HTTPStatus.OK
    payload = response.get_json()
    years = payload["years"]
    assert any(entry["year"] == 2024 for entry in years)
    assert any(entry["year"] == 2025 for entry in years)
    assert payload["default_year"] == 2025

    current_year = next(entry for entry in years if entry["year"] == 2025)
    employment_meta = current_year["employment"]
    assert employment_meta["payroll"]["default_payments_per_year"] == 14
    assert 12 in employment_meta["payroll"]["allowed_payments_per_year"]
    assert employment_meta["contributions"]["employee_rate"] >= 0

    pension_meta = current_year["pension"]
    assert pension_meta["payroll"]["allowed_payments_per_year"]
    assert pension_meta["contributions"]["employer_rate"] >= 0

    freelance_meta = current_year["freelance"]
    trade_fee = freelance_meta["trade_fee"]
    assert trade_fee["standard_amount"] == 0
    assert trade_fee.get("reduced_amount") in {None, 0}
    assert trade_fee.get("sunset") is None
    categories = freelance_meta["efka_categories"]
    assert isinstance(categories, list)
    general_category = next(
        category for category in categories if category["id"] == "general_class_1"
    )
    assert general_category["monthly_amount"] > 0
    assert "pension_monthly_amount" in general_category
    assert "health_monthly_amount" in general_category

    warnings = current_year["warnings"]
    assert isinstance(warnings, list) and warnings
    assert all(entry["id"] != "config.pending_deduction_updates" for entry in warnings)


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
    assert children_hint["description"].startswith("Καταμετρήστε")
    assert children_hint["allowances"]
    tier_labels = {threshold["label"] for threshold in children_hint["allowances"][0]["thresholds"]}
    assert "3+ εξαρτώμενα τέκνα" in tier_labels
