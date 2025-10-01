"""Unit tests for the calculation service."""

from __future__ import annotations

import pytest

from greektax.backend.app.services.calculation_service import calculate_tax


def test_calculate_tax_defaults_to_zero_summary() -> None:
    """An empty payload (besides year) should produce zeroed totals."""

    result = calculate_tax({"year": 2024})

    assert result["summary"]["income_total"] == 0.0
    assert result["summary"]["tax_total"] == 0.0
    assert result["summary"]["net_income"] == 0.0
    assert result["summary"]["net_monthly_income"] == 0.0
    assert result["summary"]["effective_tax_rate"] == 0.0
    assert result["details"] == []
    assert result["meta"] == {"year": 2024, "locale": "en"}


def test_calculate_tax_employment_only() -> None:
    """Employment income uses progressive rates and tax credit."""

    payload = {
        "year": 2024,
        "locale": "en",
        "dependents": {"children": 1},
        "employment": {"gross_income": 30_000},
    }

    result = calculate_tax(payload)

    summary = result["summary"]
    assert summary["income_total"] == pytest.approx(30_000.0)
    assert summary["tax_total"] == pytest.approx(5_090.0)
    assert summary["net_income"] == pytest.approx(24_910.0)
    assert summary["net_monthly_income"] == pytest.approx(2_075.83, rel=1e-4)
    assert summary["effective_tax_rate"] == pytest.approx(0.1697, rel=1e-4)

    assert len(result["details"]) == 1
    employment_detail = result["details"][0]
    assert employment_detail["category"] == "employment"
    assert employment_detail["gross_income"] == pytest.approx(30_000.0)
    assert employment_detail["tax_before_credits"] == pytest.approx(5_900.0)
    assert employment_detail["credits"] == pytest.approx(810.0)
    assert employment_detail["total_tax"] == pytest.approx(5_090.0)


def test_calculate_tax_accepts_monthly_employment_income() -> None:
    """Monthly salary inputs convert to annual totals and per-payment nets."""

    payload = {
        "year": 2024,
        "employment": {"monthly_income": 1_500, "payments_per_year": 14},
    }

    result = calculate_tax(payload)

    summary = result["summary"]
    assert summary["income_total"] == pytest.approx(21_000.0)
    assert summary["tax_total"] == pytest.approx(2_603.0)
    assert summary["net_income"] == pytest.approx(18_397.0)
    assert summary["net_monthly_income"] == pytest.approx(1_533.08, rel=1e-4)
    assert summary["effective_tax_rate"] == pytest.approx(0.124, rel=1e-4)

    employment_detail = result["details"][0]
    assert employment_detail["gross_income"] == pytest.approx(21_000.0)
    assert employment_detail["monthly_gross_income"] == pytest.approx(1_500.0)
    assert employment_detail["payments_per_year"] == 14
    assert employment_detail["net_income_per_payment"] == pytest.approx(1_314.07, rel=1e-4)


def test_calculate_tax_with_freelance_income() -> None:
    """Freelance profit combines progressive tax and trade fee."""

    payload = {
        "year": 2024,
        "locale": "en",
        "dependents": {"children": 0},
        "employment": {"gross_income": 20_000},
        "freelance": {
            "gross_revenue": 18_000,
            "deductible_expenses": 4_000,
            "mandatory_contributions": 3_000,
        },
    }

    result = calculate_tax(payload)

    assert result["summary"]["income_total"] == pytest.approx(34_000.0)
    assert result["summary"]["tax_total"] == pytest.approx(6_133.0)
    assert result["summary"]["net_income"] == pytest.approx(24_867.0)

    assert len(result["details"]) == 2
    employment_detail = next(
        detail for detail in result["details"] if detail["category"] == "employment"
    )
    freelance_detail = next(
        detail for detail in result["details"] if detail["category"] == "freelance"
    )

    assert employment_detail["tax_before_credits"] == pytest.approx(4_038.71)
    assert employment_detail["credits"] == pytest.approx(777.0)
    assert employment_detail["total_tax"] == pytest.approx(3_261.71)

    assert freelance_detail["taxable_income"] == pytest.approx(11_000.0)
    assert freelance_detail["tax"] == pytest.approx(2_221.29)
    assert freelance_detail["trade_fee"] == pytest.approx(650.0)
    assert freelance_detail["total_tax"] == pytest.approx(2_871.29)
    assert freelance_detail["net_income"] == pytest.approx(8_128.71)


def test_calculate_tax_respects_locale_toggle() -> None:
    """Locale toggle switches translation catalogue."""

    payload = {"year": 2024, "locale": "el", "employment": {"gross_income": 10_000}}

    result = calculate_tax(payload)

    assert result["meta"]["locale"] == "el"
    assert result["details"][0]["label"] == "Εισόδημα μισθωτών"
    assert result["summary"]["labels"]["income_total"] == "Συνολικό εισόδημα"


def test_calculate_tax_combines_employment_and_pension_credit() -> None:
    """Salary and pension income share a single tax credit."""

    payload = {
        "year": 2024,
        "dependents": {"children": 1},
        "employment": {"gross_income": 10_000},
        "pension": {"gross_income": 10_000},
    }

    result = calculate_tax(payload)

    assert result["summary"]["tax_total"] == pytest.approx(2_290.0)

    employment_detail = next(
        detail for detail in result["details"] if detail["category"] == "employment"
    )
    pension_detail = next(
        detail for detail in result["details"] if detail["category"] == "pension"
    )

    assert employment_detail["tax_before_credits"] == pytest.approx(1_550.0)
    assert pension_detail["tax_before_credits"] == pytest.approx(1_550.0)

    assert employment_detail["credits"] == pytest.approx(405.0)
    assert pension_detail["credits"] == pytest.approx(405.0)

    assert employment_detail["total_tax"] == pytest.approx(1_145.0)
    assert pension_detail["total_tax"] == pytest.approx(1_145.0)


def test_calculate_tax_with_pension_and_rental_income() -> None:
    payload = {
        "year": 2024,
        "dependents": {"children": 2},
        "pension": {"gross_income": 18_000},
        "rental": {"gross_income": 15_000, "deductible_expenses": 2_000},
    }

    result = calculate_tax(payload)

    pension_detail = next(
        detail for detail in result["details"] if detail["category"] == "pension"
    )
    rental_detail = next(
        detail for detail in result["details"] if detail["category"] == "rental"
    )

    # Pension tax: (10k * 9%) + (8k * 22%) = 900 + 1760 = 2,660
    # Credit for 2 children = 900 -> tax 1,760
    assert pension_detail["total_tax"] == pytest.approx(1_760.0)

    # Rental taxable: 15k - 2k = 13k -> 12k @15% + 1k @35% = 2,150
    assert rental_detail["taxable_income"] == pytest.approx(13_000.0)
    assert rental_detail["total_tax"] == pytest.approx(2_150.0)
    assert rental_detail["net_income"] == pytest.approx(10_850.0)

    assert result["summary"]["income_total"] == pytest.approx(33_000.0)
    assert result["summary"]["tax_total"] == pytest.approx(3_910.0)


def test_calculate_tax_with_investment_income_breakdown() -> None:
    payload = {
        "year": 2024,
        "investment": {
            "dividends": 1_000,
            "interest": 500,
            "capital_gains": 2_000,
        },
    }

    result = calculate_tax(payload)

    investment_detail = next(
        detail for detail in result["details"] if detail["category"] == "investment"
    )

    assert investment_detail["gross_income"] == pytest.approx(3_500.0)
    # Tax: 1k*5% + 500*15% + 2k*15% = 50 + 75 + 300 = 425
    assert investment_detail["total_tax"] == pytest.approx(425.0)
    assert investment_detail["net_income"] == pytest.approx(3_075.0)
    assert {item["type"] for item in investment_detail["items"]} == {
        "dividends",
        "interest",
        "capital_gains",
    }


def test_calculate_tax_includes_additional_obligations() -> None:
    payload = {
        "year": 2024,
        "obligations": {"vat": 1_250, "enfia": 320, "luxury": 880},
    }

    result = calculate_tax(payload)

    summary = result["summary"]
    assert summary["income_total"] == 0.0
    assert summary["tax_total"] == pytest.approx(2_450.0)
    assert summary["net_income"] == pytest.approx(-2_450.0)

    details = {detail["category"]: detail for detail in result["details"]}
    assert details["vat"]["total_tax"] == pytest.approx(1_250.0)
    assert details["vat"]["net_income"] == pytest.approx(-1_250.0)
    assert details["enfia"]["total_tax"] == pytest.approx(320.0)
    assert details["enfia"]["net_income"] == pytest.approx(-320.0)
    assert details["luxury"]["total_tax"] == pytest.approx(880.0)
    assert details["luxury"]["label"] == "Luxury living tax"
    assert details["luxury"]["net_income"] == pytest.approx(-880.0)


def test_calculate_tax_multi_year_credit_difference() -> None:
    base_payload = {
        "locale": "en",
        "dependents": {"children": 2},
        "employment": {"gross_income": 25_000},
    }

    result_2024 = calculate_tax({"year": 2024, **base_payload})
    result_2025 = calculate_tax({"year": 2025, **base_payload})

    tax_2024 = result_2024["summary"]["tax_total"]
    tax_2025 = result_2025["summary"]["tax_total"]

    assert tax_2025 < tax_2024
    assert result_2025["meta"]["year"] == 2025
