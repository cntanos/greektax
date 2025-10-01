"""Unit tests for the calculation service."""

from __future__ import annotations

import pytest

from greektax.backend.app.services.calculation_service import calculate_tax
from greektax.backend.config.year_config import load_year_configuration


def test_calculate_tax_defaults_to_zero_summary() -> None:
    """An empty payload (besides year) should produce zeroed totals."""

    result = calculate_tax({"year": 2024})

    assert result["summary"]["income_total"] == 0.0
    assert result["summary"]["tax_total"] == 0.0
    assert result["summary"]["net_income"] == 0.0
    assert result["summary"]["net_monthly_income"] == 0.0
    assert result["summary"]["average_monthly_tax"] == 0.0
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
    assert summary["net_income"] == pytest.approx(20_749.0)
    assert summary["net_monthly_income"] == pytest.approx(1_729.08, rel=1e-4)
    assert summary["average_monthly_tax"] == pytest.approx(424.17, rel=1e-4)
    assert summary["effective_tax_rate"] == pytest.approx(0.1697, rel=1e-4)

    assert len(result["details"]) == 1
    employment_detail = result["details"][0]
    assert employment_detail["category"] == "employment"
    assert employment_detail["gross_income"] == pytest.approx(30_000.0)
    assert employment_detail["tax_before_credits"] == pytest.approx(5_900.0)
    assert employment_detail["credits"] == pytest.approx(810.0)
    assert employment_detail["total_tax"] == pytest.approx(5_090.0)
    assert employment_detail["employee_contributions"] == pytest.approx(4_161.0)
    assert employment_detail["employer_contributions"] == pytest.approx(6_729.0)


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
    assert summary["net_income"] == pytest.approx(15_484.3, rel=1e-4)
    assert summary["net_monthly_income"] == pytest.approx(1_290.36, rel=1e-4)
    assert summary["average_monthly_tax"] == pytest.approx(216.92, rel=1e-4)
    assert summary["effective_tax_rate"] == pytest.approx(0.124, rel=1e-4)

    employment_detail = result["details"][0]
    assert employment_detail["gross_income"] == pytest.approx(21_000.0)
    assert employment_detail["monthly_gross_income"] == pytest.approx(1_500.0)
    assert employment_detail["payments_per_year"] == 14
    assert employment_detail["gross_income_per_payment"] == pytest.approx(1_500.0)
    assert employment_detail["net_income_per_payment"] == pytest.approx(1_106.02, rel=1e-4)
    assert employment_detail["employee_contributions_per_payment"] == pytest.approx(208.05, rel=1e-4)
    assert employment_detail["employer_contributions_per_payment"] == pytest.approx(336.45, rel=1e-4)


def test_calculate_tax_supports_manual_employee_contributions() -> None:
    """Extra EFKA payments reduce net income and appear in the breakdown."""

    payload = {
        "year": 2024,
        "employment": {
            "monthly_income": 1_500,
            "payments_per_year": 14,
            "employee_contributions": 500,
        },
    }

    result = calculate_tax(payload)

    summary = result["summary"]
    assert summary["income_total"] == pytest.approx(21_000.0)
    assert summary["net_income"] == pytest.approx(14_984.3, rel=1e-4)

    employment_detail = result["details"][0]
    assert employment_detail["employee_contributions"] == pytest.approx(3_412.7, rel=1e-4)
    assert employment_detail["employee_contributions_manual"] == pytest.approx(500.0)


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
    assert result["summary"]["net_income"] == pytest.approx(22_093.0)

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
    assert employment_detail["employee_contributions"] == pytest.approx(2_774.0)

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
    assert result["summary"]["net_income"] == pytest.approx(16_323.0)

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
    assert employment_detail["employee_contributions"] == pytest.approx(1_387.0)


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


def test_calculate_tax_with_freelance_category_contributions() -> None:
    """EFKA category metadata populates contribution breakdowns."""

    payload = {
        "year": 2024,
        "freelance": {
            "profit": 30_000,
            "efka_category": "general_class_1",
            "efka_months": 6,
            "mandatory_contributions": 500,
            "auxiliary_contributions": 120,
        },
    }

    config = load_year_configuration(2024)
    category = next(
        entry for entry in config.freelance.efka_categories if entry.id == "general_class_1"
    )
    expected_category_contribution = category.monthly_amount * 6
    expected_deductible = expected_category_contribution + 500 + 120

    result = calculate_tax(payload)

    freelance_detail = result["details"][0]
    assert freelance_detail["category"] == "freelance"
    assert freelance_detail["category_contributions"] == pytest.approx(
        expected_category_contribution
    )
    assert freelance_detail["deductible_contributions"] == pytest.approx(
        expected_deductible
    )
    assert freelance_detail["additional_contributions"] == pytest.approx(500.0)
    assert freelance_detail["auxiliary_contributions"] == pytest.approx(120.0)
    assert "lump_sum_contributions" not in freelance_detail
    assert freelance_detail["trade_fee"] == pytest.approx(
        config.freelance.trade_fee.standard_amount
    )


def test_calculate_tax_with_engineer_lump_sum_contributions() -> None:
    """Engineer categories include auxiliary and lump-sum contributions."""

    config = load_year_configuration(2024)
    category = next(
        entry for entry in config.freelance.efka_categories if entry.id == "engineer_class_1"
    )
    months = 12
    auxiliary_total = (category.auxiliary_monthly_amount or 0) * months
    lump_sum_total = (category.lump_sum_monthly_amount or 0) * months

    payload = {
        "year": 2024,
        "freelance": {
            "profit": 40_000,
            "efka_category": "engineer_class_1",
            "efka_months": months,
            "auxiliary_contributions": auxiliary_total,
            "lump_sum_contributions": lump_sum_total,
        },
    }

    result = calculate_tax(payload)
    freelance_detail = result["details"][0]

    expected_category = category.monthly_amount * months
    expected_total = expected_category + auxiliary_total + lump_sum_total

    assert freelance_detail["category_contributions"] == pytest.approx(expected_category)
    assert freelance_detail["auxiliary_contributions"] == pytest.approx(auxiliary_total)
    assert freelance_detail["lump_sum_contributions"] == pytest.approx(lump_sum_total)
    assert freelance_detail["deductible_contributions"] == pytest.approx(expected_total)


def test_calculate_tax_applies_deductions_across_components() -> None:
    """Itemised deductions are distributed proportionally across taxable income."""

    payload = {
        "year": 2024,
        "locale": "en",
        "employment": {"gross_income": 30_000},
        "agricultural": {"gross_revenue": 12_000, "deductible_expenses": 2_000},
        "deductions": {
            "donations": 2_000,
            "medical": 1_000,
            "education": 1_000,
            "insurance": 1_000,
        },
    }

    result = calculate_tax(payload)

    employment_detail = next(
        detail for detail in result["details"] if detail["category"] == "employment"
    )
    agricultural_detail = next(
        detail for detail in result["details"] if detail["category"] == "agricultural"
    )

    assert employment_detail["deductions_applied"] == pytest.approx(3_750.0)
    assert employment_detail["taxable_income"] == pytest.approx(26_250.0)
    assert agricultural_detail["deductions_applied"] == pytest.approx(1_250.0)
    assert agricultural_detail["taxable_income"] == pytest.approx(8_750.0)

    summary = result["summary"]
    assert summary["deductions_entered"] == pytest.approx(5_000.0)
    assert summary["deductions_applied"] == pytest.approx(5_000.0)


def test_calculate_tax_with_agricultural_and_other_income() -> None:
    """Agricultural and other income categories produce dedicated details."""

    payload = {
        "year": 2024,
        "agricultural": {"gross_revenue": 15_000, "deductible_expenses": 2_000},
        "other": {"taxable_income": 5_000},
    }

    result = calculate_tax(payload)

    agricultural_detail = next(
        detail for detail in result["details"] if detail["category"] == "agricultural"
    )
    other_detail = next(
        detail for detail in result["details"] if detail["category"] == "other"
    )

    assert agricultural_detail["taxable_income"] == pytest.approx(13_000.0)
    assert agricultural_detail["total_tax"] == pytest.approx(1_921.11, rel=1e-4)
    assert other_detail["taxable_income"] == pytest.approx(5_000.0)
    assert other_detail["total_tax"] == pytest.approx(738.89, rel=1e-4)

    summary = result["summary"]
    assert summary["income_total"] == pytest.approx(20_000.0)
    assert summary["tax_total"] == pytest.approx(2_660.0)


def test_calculate_tax_trade_fee_reduction_rules() -> None:
    """Trade fee respects optional inclusion and reduction toggles."""

    base_payload = {
        "year": 2024,
        "freelance": {
            "profit": 12_000,
            "efka_category": "general_class_1",
            "trade_fee_location": "standard",
            "years_active": 2,
            "newly_self_employed": True,
        },
    }

    config = load_year_configuration(2024)
    trade_fee_config = config.freelance.trade_fee

    reduced_fee_result = calculate_tax(base_payload)
    reduced_detail = reduced_fee_result["details"][0]
    assert reduced_detail["trade_fee"] == pytest.approx(
        trade_fee_config.reduced_amount or trade_fee_config.standard_amount
    )

    no_fee_payload = {"year": 2024, "freelance": {**base_payload["freelance"], "include_trade_fee": False}}
    no_fee_result = calculate_tax(no_fee_payload)
    no_fee_detail = no_fee_result["details"][0]
    assert no_fee_detail["trade_fee"] == pytest.approx(0.0)
    expected_difference = reduced_detail["trade_fee"]
    assert reduced_detail["total_tax"] == pytest.approx(
        no_fee_detail["total_tax"] + expected_difference
    )
