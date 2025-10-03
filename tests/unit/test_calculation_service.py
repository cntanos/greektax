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


def test_calculate_tax_with_withholding_tax_balance_due() -> None:
    """Withholding reduces the net tax payable and surfaces in the summary."""

    payload = {
        "year": 2024,
        "employment": {"gross_income": 30_000},
        "withholding_tax": 2_000,
    }

    result = calculate_tax(payload)

    summary = result["summary"]
    assert summary["tax_total"] == pytest.approx(5_123.0)
    assert summary["withholding_tax"] == pytest.approx(2_000.0)
    assert summary["balance_due"] == pytest.approx(3_123.0)
    assert summary["balance_due_is_refund"] is False
    assert summary["labels"]["balance_due"] == "Net tax due"


def test_calculate_tax_with_withholding_tax_refund() -> None:
    """Withholding greater than tax due produces a refund summary."""

    payload = {
        "year": 2024,
        "employment": {"gross_income": 30_000},
        "withholding_tax": 6_000,
    }

    result = calculate_tax(payload)

    summary = result["summary"]
    assert summary["tax_total"] == pytest.approx(5_123.0)
    assert summary["withholding_tax"] == pytest.approx(6_000.0)
    assert summary["balance_due"] == pytest.approx(877.0)
    assert summary["balance_due_is_refund"] is True
    assert summary["labels"]["balance_due"] == "Refund due"


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
    assert result["summary"]["tax_total"] == pytest.approx(5_483.0)
    assert result["summary"]["net_income"] == pytest.approx(22_743.0)

    assert len(result["details"]) == 2
    employment_detail = next(
        detail for detail in result["details"] if detail["category"] == "employment"
    )
    freelance_detail = next(
        detail for detail in result["details"] if detail["category"] == "freelance"
    )

    assert employment_detail["tax_before_credits"] == pytest.approx(4_038.71)
    assert employment_detail["credits"] == pytest.approx(501.29, rel=1e-4)
    assert employment_detail["total_tax"] == pytest.approx(3_537.42, rel=1e-4)
    assert employment_detail["employee_contributions"] == pytest.approx(2_774.0)

    assert freelance_detail["taxable_income"] == pytest.approx(11_000.0)
    assert freelance_detail["tax"] == pytest.approx(1_945.58, rel=1e-4)
    assert freelance_detail["trade_fee"] == pytest.approx(0.0)
    assert freelance_detail["total_tax"] == pytest.approx(1_945.58, rel=1e-4)
    assert freelance_detail["net_income"] == pytest.approx(9_054.42, rel=1e-4)


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
    assert freelance_detail["trade_fee"] == pytest.approx(0.0)


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
    """Itemised deductions now translate into capped tax credits."""

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

    assert employment_detail["deductions_applied"] == pytest.approx(600.0)
    assert employment_detail["taxable_income"] == pytest.approx(30_000.0)
    assert "deductions_applied" not in agricultural_detail
    assert agricultural_detail["taxable_income"] == pytest.approx(10_000.0)

    summary = result["summary"]
    assert summary["deductions_entered"] == pytest.approx(5_000.0)
    assert summary["deductions_applied"] == pytest.approx(600.0)

    breakdown = summary.get("deductions_breakdown")
    assert breakdown is not None
    donations = next(item for item in breakdown if item["type"] == "donations")
    assert donations["credit_applied"] == pytest.approx(400.0)
    medical = next(item for item in breakdown if item["type"] == "medical")
    assert medical["credit_applied"] == pytest.approx(0.0)


def test_calculate_tax_applies_donation_credit_to_freelance_tax() -> None:
    """Donation credits now reduce freelance progressive tax directly."""

    base_payload = {
        "year": 2024,
        "freelance": {"profit": 20_000},
    }

    baseline = calculate_tax(base_payload)
    with_donation = calculate_tax(
        {**base_payload, "deductions": {"donations": 100}}
    )

    baseline_tax = baseline["summary"]["tax_total"]
    donation_tax = with_donation["summary"]["tax_total"]

    assert baseline_tax - donation_tax == pytest.approx(20.0)

    breakdown = with_donation["summary"].get("deductions_breakdown")
    assert breakdown is not None
    donation_entry = next(item for item in breakdown if item["type"] == "donations")
    assert donation_entry["credit_applied"] == pytest.approx(20.0)


def test_calculate_tax_applies_medical_credit_threshold_for_freelance() -> None:
    """Medical credits apply the 5% threshold before reducing tax."""

    base_payload = {
        "year": 2024,
        "freelance": {"profit": 20_000},
    }

    baseline = calculate_tax(base_payload)
    with_medical = calculate_tax(
        {**base_payload, "deductions": {"medical": 2_500}}
    )

    baseline_tax = baseline["summary"]["tax_total"]
    medical_tax = with_medical["summary"]["tax_total"]

    assert baseline_tax - medical_tax == pytest.approx(150.0)

    breakdown = with_medical["summary"].get("deductions_breakdown")
    assert breakdown is not None
    medical_entry = next(item for item in breakdown if item["type"] == "medical")
    assert medical_entry["eligible"] == pytest.approx(1_500.0)
    assert medical_entry["credit_applied"] == pytest.approx(150.0)


def test_calculate_tax_trade_fee_auto_exemption_by_year() -> None:
    """Trade fee remains waived from 2024 onwards once the abolition takes effect."""

    payload_2024 = {"year": 2024, "freelance": {"profit": 12_000}}
    result_2024 = calculate_tax(payload_2024)
    freelance_2024 = next(
        detail for detail in result_2024["details"] if detail["category"] == "freelance"
    )
    assert freelance_2024["trade_fee"] == pytest.approx(0.0)

    payload_2025 = {"year": 2025, "freelance": {"profit": 12_000}}
    result_2025 = calculate_tax(payload_2025)
    freelance_2025 = next(
        detail for detail in result_2025["details"] if detail["category"] == "freelance"
    )
    assert freelance_2025["trade_fee"] == pytest.approx(0.0)

    assert result_2025["summary"]["tax_total"] == pytest.approx(
        result_2024["summary"]["tax_total"]
    )


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


def test_agricultural_only_income_receives_tax_credit() -> None:
    """Sole agricultural income qualifies for the base tax credit in 2025."""

    config = load_year_configuration(2025)
    base_credit = config.employment.tax_credit.amount_for_children(0)

    payload = {
        "year": 2025,
        "agricultural": {
            "gross_revenue": 12_000,
            "deductible_expenses": 2_000,
        },
    }

    result = calculate_tax(payload)

    agricultural_detail = next(
        detail for detail in result["details"] if detail["category"] == "agricultural"
    )

    taxable_income = agricultural_detail["taxable_income"]

    def _progressive_tax(amount: float) -> float:
        total = 0.0
        lower = 0.0
        for bracket in config.employment.brackets:
            upper = bracket.upper_bound
            rate = bracket.rate
            if upper is None or amount <= upper:
                total += (amount - lower) * rate
                break
            total += (upper - lower) * rate
            lower = upper
        return total

    expected_before_credit = _progressive_tax(taxable_income)
    expected_credit = min(base_credit, expected_before_credit)
    expected_tax = expected_before_credit - expected_credit

    assert agricultural_detail["tax_before_credits"] == pytest.approx(
        expected_before_credit
    )
    assert agricultural_detail["credits"] == pytest.approx(expected_credit)
    assert agricultural_detail["tax"] == pytest.approx(expected_tax)
    assert result["summary"]["tax_total"] == pytest.approx(expected_tax)


def test_professional_farmer_receives_dependent_credit() -> None:
    """Professional farmers retain the credit even with other income."""

    config = load_year_configuration(2025)
    dependent_credit = config.employment.tax_credit.amount_for_children(2)

    payload = {
        "year": 2025,
        "dependents": {"children": 2},
        "agricultural": {
            "gross_revenue": 28_000,
            "deductible_expenses": 3_000,
            "professional_farmer": True,
        },
        "other": {"taxable_income": 4_000},
    }

    result = calculate_tax(payload)

    agricultural_detail = next(
        detail for detail in result["details"] if detail["category"] == "agricultural"
    )
    other_detail = next(
        detail for detail in result["details"] if detail["category"] == "other"
    )

    assert agricultural_detail["credits"] == pytest.approx(
        min(dependent_credit, agricultural_detail["tax_before_credits"])
    )
    if "credits" in other_detail:
        assert other_detail["credits"] == pytest.approx(0.0)
    else:
        assert "credits" not in other_detail

def test_calculate_tax_trade_fee_reduction_rules() -> None:
    """Trade fee toggles keep the amount at zero after the abolition."""

    base_payload = {
        "year": 2025,
        "freelance": {
            "profit": 12_000,
            "efka_category": "general_class_1",
            "trade_fee_location": "standard",
            "years_active": 2,
            "newly_self_employed": True,
        },
    }

    config = load_year_configuration(2025)
    trade_fee_config = config.freelance.trade_fee

    reduced_fee_result = calculate_tax(base_payload)
    reduced_detail = reduced_fee_result["details"][0]
    assert reduced_detail["trade_fee"] == pytest.approx(
        trade_fee_config.reduced_amount or trade_fee_config.standard_amount
    )

    no_fee_payload = {"year": 2025, "freelance": {**base_payload["freelance"], "include_trade_fee": False}}
    no_fee_result = calculate_tax(no_fee_payload)
    no_fee_detail = no_fee_result["details"][0]
    assert no_fee_detail["trade_fee"] == pytest.approx(0.0)
    expected_difference = reduced_detail["trade_fee"]
    assert reduced_detail["total_tax"] == pytest.approx(
        no_fee_detail["total_tax"] + expected_difference
    )
