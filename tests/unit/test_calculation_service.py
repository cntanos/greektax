"""Unit tests for the calculation service."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
from pydantic import ValidationError

from greektax.backend.app.models import CalculationRequest, NET_INCOME_INPUT_ERROR
from greektax.backend.app.services.calculation_service import calculate_tax
from greektax.backend.config.year_config import YearConfiguration, load_year_configuration


def _progressive_tax(amount: float, brackets, *, dependants: int = 0) -> float:
    """Compute progressive tax for the provided amount using the supplied brackets."""

    total = 0.0
    lower_bound = 0.0

    for bracket in brackets:
        upper = bracket.upper_bound
        rate = bracket.rate
        rate_for_dependants = getattr(bracket, "rate_for_dependants", None)
        if callable(rate_for_dependants):
            rate = rate_for_dependants(dependants)
        if upper is None or amount <= upper:
            total += (amount - lower_bound) * rate
            break

        total += (upper - lower_bound) * rate
        lower_bound = upper

    return total


def _employment_contribution_base(
    config: YearConfiguration,
    gross_income: float,
    monthly_income: float | None,
    payments_per_year: int | None,
) -> float:
    """Return the annual income base used for employment contributions."""

    salary_cap = config.employment.contributions.monthly_salary_cap
    payments = payments_per_year or config.employment.payroll.default_payments_per_year

    if not payments or payments <= 0:
        return gross_income

    monthly = monthly_income
    if monthly is None:
        monthly = gross_income / payments if payments else None

    if (
        salary_cap is not None
        and salary_cap > 0
        and monthly is not None
    ):
        capped_annual = salary_cap * payments
        return min(gross_income, capped_annual)

    return gross_income


def _employment_expectations(
    year: int,
    gross_income: float,
    *,
    children: int = 0,
    monthly_income: float | None = None,
    payments_per_year: int | None = None,
    include_social: bool = True,
    manual_contributions: float = 0.0,
) -> dict[str, float]:
    """Return expected employment tax metrics for the given inputs."""

    config = load_year_configuration(year)
    employment = config.employment

    employee_rate = employment.contributions.employee_rate
    employer_rate = employment.contributions.employer_rate
    contribution_base = _employment_contribution_base(
        config, gross_income, monthly_income, payments_per_year
    )
    auto_employee_contrib = (
        contribution_base * employee_rate if include_social else 0.0
    )
    manual_requested = manual_contributions if include_social else 0.0
    max_employee_contrib = auto_employee_contrib if include_social else 0.0
    manual_contrib = manual_requested
    total_employee_contrib = auto_employee_contrib + manual_requested
    if max_employee_contrib and total_employee_contrib > max_employee_contrib:
        manual_contrib = max(max_employee_contrib - auto_employee_contrib, 0.0)
        total_employee_contrib = max_employee_contrib
    employee_contrib = total_employee_contrib
    employer_contrib = contribution_base * employer_rate if include_social else 0.0

    taxable_income = (
        gross_income - employee_contrib if include_social else gross_income
    )
    if taxable_income < 0:
        taxable_income = 0.0

    tax_before_credit = _progressive_tax(
        taxable_income, employment.brackets, dependants=children
    )
    credit_amount = employment.tax_credit.amount_for_children(children)
    credit_reduction = 0.0
    if gross_income > 12_000:
        credit_reduction = ((gross_income - 12_000) / 1_000) * 20.0
    credit_after_reduction = max(credit_amount - credit_reduction, 0.0)
    credit_applied = min(credit_after_reduction, tax_before_credit)
    tax_after_credit = tax_before_credit - credit_applied

    net_income = gross_income - tax_after_credit
    if include_social:
        net_income -= employee_contrib

    effective_rate = (tax_after_credit / gross_income) if gross_income else 0.0

    employer_cost = gross_income + employer_contrib
    employer_cost_per_payment = None
    if payments_per_year:
        employer_cost_per_payment = employer_cost / payments_per_year

    return {
        "tax_before_credit": tax_before_credit,
        "credit": credit_applied,
        "tax": tax_after_credit,
        "employee_contrib": employee_contrib,
        "employer_contrib": employer_contrib,
        "employer_cost": employer_cost,
        "employer_cost_per_payment": employer_cost_per_payment,
        "net_income": net_income,
        "net_monthly": net_income / 12 if gross_income else 0.0,
        "avg_monthly_tax": tax_after_credit / 12 if gross_income else 0.0,
        "effective_rate": round(effective_rate, 4),
        "taxable": taxable_income,
    }


def test_employment_contribution_rates_updated_for_2025() -> None:
    """Employment contribution tables include the 2025 rate and cap revisions."""

    config_2024 = load_year_configuration(2024)
    contributions_2024 = config_2024.employment.contributions

    assert contributions_2024.employee_rate == pytest.approx(0.1387)
    assert contributions_2024.employer_rate == pytest.approx(0.2229)
    assert contributions_2024.monthly_salary_cap == pytest.approx(7126.94)

    config_2025 = load_year_configuration(2025)
    contributions_2025 = config_2025.employment.contributions

    assert contributions_2025.employee_rate == pytest.approx(0.1337)
    assert contributions_2025.employer_rate == pytest.approx(0.2179)
    assert contributions_2025.monthly_salary_cap == pytest.approx(7572.62)


def _freelance_expectations(request: CalculationRequest) -> dict[str, Any]:
    """Return expected freelance and employment metrics for the mixed payload."""

    config = load_year_configuration(request.year)

    employment_gross = request.employment.gross_income
    dependents = request.dependents.children

    freelance_section = request.freelance
    gross_after_expenses = (
        freelance_section.gross_revenue - freelance_section.deductible_expenses
    )
    contributions = freelance_section.mandatory_contributions

    include_social = request.employment.include_social_contributions

    contribution_base = _employment_contribution_base(
        config,
        employment_gross,
        request.employment.monthly_income,
        request.employment.payments_per_year,
    )
    auto_employee_contrib = (
        contribution_base * config.employment.contributions.employee_rate
        if include_social
        else 0.0
    )
    employer_contrib = (
        contribution_base * config.employment.contributions.employer_rate
        if include_social
        else 0.0
    )
    manual_requested = (
        request.employment.employee_contributions if include_social else 0.0
    )
    max_employee_contrib = auto_employee_contrib if include_social else 0.0
    manual_employee_contrib = manual_requested
    total_employee_contrib = auto_employee_contrib + manual_requested
    if max_employee_contrib and total_employee_contrib > max_employee_contrib:
        manual_employee_contrib = max(max_employee_contrib - auto_employee_contrib, 0.0)
        total_employee_contrib = max_employee_contrib

    employment_taxable = (
        employment_gross - total_employee_contrib if include_social else employment_gross
    )
    if employment_taxable < 0:
        employment_taxable = 0.0

    freelance_taxable = gross_after_expenses - contributions
    total_taxable = employment_taxable + freelance_taxable

    total_tax_before_credit = _progressive_tax(
        total_taxable,
        config.employment.brackets,
        dependants=dependents,
    )
    credit_amount = config.employment.tax_credit.amount_for_children(dependents)
    credit_reduction = 0.0
    if employment_gross > 12_000:
        credit_reduction = ((employment_gross - 12_000) / 1_000) * 20.0
    credit_after_reduction = max(credit_amount - credit_reduction, 0.0)
    credit_applied = min(credit_after_reduction, total_tax_before_credit)

    employment_share = (
        employment_taxable / total_taxable if total_taxable else 0.0
    )
    employment_tax_before_credit = total_tax_before_credit * employment_share
    freelance_tax_before_credit = (
        total_tax_before_credit - employment_tax_before_credit
    )

    employment_credit = (
        credit_applied * (employment_tax_before_credit / total_tax_before_credit)
        if total_tax_before_credit
        else 0.0
    )
    freelance_credit = credit_applied - employment_credit

    employment_tax = employment_tax_before_credit - employment_credit
    freelance_tax = freelance_tax_before_credit - freelance_credit

    employment_employee_contrib = total_employee_contrib
    employment_employer_contrib = employer_contrib

    employment_net = employment_gross - employment_tax
    if include_social:
        employment_net -= employment_employee_contrib
    freelance_net = gross_after_expenses - freelance_tax - contributions

    total_income = employment_gross + gross_after_expenses
    total_tax = employment_tax + freelance_tax
    total_net = employment_net + freelance_net

    return {
        "summary": {
            "income": total_income,
            "taxable": total_taxable,
            "tax": total_tax,
            "net": total_net,
            "net_monthly": total_net / 12,
            "avg_monthly_tax": total_tax / 12,
            "effective_rate": round(total_tax / total_income, 4),
        },
        "employment": {
            "gross": employment_gross,
            "tax_before_credit": employment_tax_before_credit,
            "credit": employment_credit,
            "tax": employment_tax,
            "employee_contrib": employment_employee_contrib,
            "employer_contrib": employment_employer_contrib,
            "net": employment_net,
        },
        "freelance": {
            "gross": gross_after_expenses,
            "taxable": freelance_taxable,
            "tax": freelance_tax,
            "credit": freelance_credit,
            "net": freelance_net,
            "contributions": contributions,
        },
    }


def test_calculate_tax_rejects_invalid_numbers() -> None:
    """Payloads with invalid numeric data surface clear validation errors."""

    with pytest.raises(ValueError) as error:
        calculate_tax({"year": 2024, "employment": {"gross_income": -10}})

    message = str(error.value)
    assert "employment.gross_income" in message
    assert "Invalid calculation payload" in message


@pytest.mark.parametrize("field", ["net_income", "net_monthly_income"])
def test_calculation_request_rejects_net_income_inputs(field: str) -> None:
    """Employment payloads should reject legacy net income fields."""

    with pytest.raises(ValidationError) as exc_info:
        CalculationRequest.model_validate({"year": 2024, "employment": {field: 1_000}})

    message = str(exc_info.value)
    assert NET_INCOME_INPUT_ERROR in message


@pytest.mark.parametrize("field", ["net_income", "net_monthly_income"])
def test_calculate_tax_preserves_net_income_validation_error(field: str) -> None:
    """Service-level validation should surface the net income error message."""

    payload = {"year": 2024, "employment": {field: 1_000}}

    with pytest.raises(ValueError) as exc_info:
        calculate_tax(payload)

    message = str(exc_info.value)
    assert NET_INCOME_INPUT_ERROR in message


def test_calculate_tax_accepts_request_model_instance() -> None:
    """The service can operate directly on a validated request model."""

    request_model = CalculationRequest.model_validate(
        {"year": 2024, "employment": {"gross_income": 12_000}}
    )

    result = calculate_tax(request_model)

    expected = _employment_expectations(request_model.year, request_model.employment.gross_income)

    assert result["meta"] == {"year": 2024, "locale": "en"}
    assert result["summary"]["income_total"] == pytest.approx(12_000.0)
    assert result["summary"]["taxable_income"] == pytest.approx(expected["taxable"])


def test_calculate_tax_defaults_to_zero_summary() -> None:
    """An empty payload (besides year) should produce zeroed totals."""

    request = CalculationRequest.model_validate({"year": 2024})

    result = calculate_tax(request)

    assert result["summary"]["income_total"] == 0.0
    assert result["summary"]["taxable_income"] == 0.0
    assert result["summary"]["tax_total"] == 0.0
    assert result["summary"]["net_income"] == 0.0
    assert result["summary"]["net_monthly_income"] == 0.0
    assert result["summary"]["average_monthly_tax"] == 0.0
    assert result["summary"]["effective_tax_rate"] == 0.0
    assert result["details"] == []
    assert result["meta"] == {"year": 2024, "locale": "en"}


def test_calculate_tax_employment_only() -> None:
    """Employment income uses progressive rates and tax credit."""

    request = CalculationRequest.model_validate(
        {
            "year": 2024,
            "locale": "en",
            "dependents": {"children": 1},
            "employment": {"gross_income": 30_000},
        }
    )

    result = calculate_tax(request)

    gross_income = request.employment.gross_income
    expected = _employment_expectations(
        request.year, gross_income, children=request.dependents.children
    )

    summary = result["summary"]
    assert summary["income_total"] == pytest.approx(gross_income)
    assert summary["taxable_income"] == pytest.approx(expected["taxable"])
    assert summary["tax_total"] == pytest.approx(expected["tax"], rel=1e-4)
    assert summary["net_income"] == pytest.approx(expected["net_income"])
    assert summary["net_monthly_income"] == pytest.approx(
        expected["net_monthly"], rel=1e-4
    )
    assert summary["average_monthly_tax"] == pytest.approx(
        expected["avg_monthly_tax"], rel=1e-4
    )
    assert summary["effective_tax_rate"] == pytest.approx(
        expected["effective_rate"], rel=1e-4
    )

    assert len(result["details"]) == 1
    employment_detail = result["details"][0]
    assert employment_detail["category"] == "employment"
    assert employment_detail["gross_income"] == pytest.approx(gross_income)
    assert employment_detail["tax_before_credits"] == pytest.approx(
        expected["tax_before_credit"], rel=1e-4
    )
    assert employment_detail["credits"] == pytest.approx(
        expected["credit"], rel=1e-4
    )
    assert employment_detail["total_tax"] == pytest.approx(expected["tax"])
    assert employment_detail["employee_contributions"] == pytest.approx(
        expected["employee_contrib"], rel=1e-4
    )
    assert employment_detail["employer_contributions"] == pytest.approx(
        expected["employer_contrib"], rel=1e-4
    )
    assert employment_detail["employer_cost"] == pytest.approx(
        expected["employer_cost"], rel=1e-4
    )


def test_employment_tax_credit_not_reduced_below_threshold() -> None:
    """Gross salaries below €12k retain the full family tax credit."""

    request = CalculationRequest.model_validate(
        {
            "year": 2024,
            "dependents": {"children": 0},
            "employment": {"gross_income": 11_900},
        }
    )

    result = calculate_tax(request)
    employment_detail = result["details"][0]

    config = load_year_configuration(request.year)
    base_credit = config.employment.tax_credit.amount_for_children(
        request.dependents.children
    )

    assert employment_detail["credits"] == pytest.approx(base_credit)


def test_employment_tax_credit_reduced_using_gross_income() -> None:
    """Salary credits are reduced based on gross income above €12k and never negative."""

    request = CalculationRequest.model_validate(
        {
            "year": 2024,
            "dependents": {"children": 0},
            "employment": {"gross_income": 12_100},
        }
    )

    result = calculate_tax(request)
    employment_detail = result["details"][0]

    config = load_year_configuration(request.year)
    base_credit = config.employment.tax_credit.amount_for_children(
        request.dependents.children
    )
    gross_income = request.employment.gross_income
    reduction = ((gross_income - 12_000) / 1_000) * 20.0
    expected_credit = max(base_credit - reduction, 0.0)

    assert employment_detail["taxable_income"] < 12_000
    assert employment_detail["credits"] == pytest.approx(expected_credit)
    assert employment_detail["credits"] >= 0.0


def test_calculate_tax_with_withholding_tax_balance_due() -> None:
    """Withholding reduces the net tax payable and surfaces in the summary."""

    request = CalculationRequest.model_validate(
        {
            "year": 2024,
            "employment": {"gross_income": 30_000},
            "withholding_tax": 2_000,
        }
    )

    result = calculate_tax(request)

    expected = _employment_expectations(request.year, 30_000)
    withholding = request.withholding_tax
    expected_balance_due = expected["tax"] - withholding

    summary = result["summary"]
    assert summary["tax_total"] == pytest.approx(expected["tax"], rel=1e-4)
    assert summary["taxable_income"] == pytest.approx(expected["taxable"])
    assert summary["withholding_tax"] == pytest.approx(withholding)
    assert summary["balance_due"] == pytest.approx(expected_balance_due)
    assert summary["balance_due_is_refund"] is False
    assert summary["net_income"] == pytest.approx(expected["net_income"])
    assert summary["labels"]["balance_due"] == "Net tax due"


def test_calculate_tax_with_withholding_tax_refund() -> None:
    """Withholding greater than tax due produces a refund summary."""

    request = CalculationRequest.model_validate(
        {
            "year": 2024,
            "employment": {"gross_income": 30_000},
            "withholding_tax": 6_000,
        }
    )

    result = calculate_tax(request)

    expected = _employment_expectations(request.year, 30_000)
    withholding = request.withholding_tax
    expected_refund = abs(expected["tax"] - withholding)

    summary = result["summary"]
    assert summary["tax_total"] == pytest.approx(expected["tax"], rel=1e-4)
    assert summary["taxable_income"] == pytest.approx(expected["taxable"])
    assert summary["withholding_tax"] == pytest.approx(withholding)
    assert summary["balance_due"] == pytest.approx(expected_refund)
    assert summary["balance_due_is_refund"] is True
    assert summary["net_income"] == pytest.approx(expected["net_income"])
    assert summary["labels"]["balance_due"] == "Refund due"


@pytest.mark.parametrize("payments_per_year", [14, 12])
def test_calculate_tax_accepts_monthly_employment_income(
    payments_per_year: int,
) -> None:
    """Monthly salary inputs convert to annual totals and per-payment nets."""

    request = CalculationRequest.model_validate(
        {
            "year": 2024,
            "employment": {
                "monthly_income": 1_500,
                "payments_per_year": payments_per_year,
            },
        }
    )

    result = calculate_tax(request)

    monthly_income = request.employment.monthly_income or 0.0
    payments = request.employment.payments_per_year or 0
    gross_income = monthly_income * payments
    expected = _employment_expectations(
        2024,
        gross_income,
        monthly_income=monthly_income,
        payments_per_year=payments,
    )
    expected_employee_per_payment = expected["employee_contrib"] / payments
    expected_employer_per_payment = expected["employer_contrib"] / payments
    expected_net_per_payment = expected["net_income"] / payments

    summary = result["summary"]
    assert summary["income_total"] == pytest.approx(gross_income)
    assert summary["taxable_income"] == pytest.approx(expected["taxable"])
    assert summary["tax_total"] == pytest.approx(expected["tax"], rel=1e-4)
    assert summary["net_income"] == pytest.approx(expected["net_income"], rel=1e-4)
    assert summary["net_monthly_income"] == pytest.approx(
        expected["net_monthly"], rel=1e-4
    )
    assert summary["average_monthly_tax"] == pytest.approx(
        expected["avg_monthly_tax"], rel=1e-4
    )
    assert summary["effective_tax_rate"] == pytest.approx(
        expected["effective_rate"], rel=1e-4
    )

    employment_detail = result["details"][0]
    assert employment_detail["gross_income"] == pytest.approx(gross_income)
    assert employment_detail["monthly_gross_income"] == pytest.approx(monthly_income)
    assert employment_detail["payments_per_year"] == payments
    assert employment_detail["gross_income_per_payment"] == pytest.approx(
        gross_income / payments
    )
    assert employment_detail["net_income_per_payment"] == pytest.approx(
        expected_net_per_payment, rel=1e-4
    )
    assert employment_detail["employee_contributions_per_payment"] == pytest.approx(
        expected_employee_per_payment, rel=1e-4
    )
    assert employment_detail["employer_contributions_per_payment"] == pytest.approx(
        expected_employer_per_payment, rel=1e-4
    )
    assert employment_detail["employer_cost"] == pytest.approx(
        expected["employer_cost"], rel=1e-4
    )
    assert employment_detail["employer_cost_per_payment"] == pytest.approx(
        expected["employer_cost_per_payment"], rel=1e-4
    )


@pytest.mark.parametrize(
    ("year", "payments_per_year"),
    [(2024, 14), (2024, 12), (2025, 14), (2025, 12)],
)
def test_employment_contributions_respect_salary_cap(
    year: int, payments_per_year: int
) -> None:
    """Employment contributions stop increasing once the statutory cap is reached."""

    request = CalculationRequest.model_validate(
        {
            "year": year,
            "employment": {
                "monthly_income": 9_000,
                "payments_per_year": payments_per_year,
            },
        }
    )

    result = calculate_tax(request)

    monthly_income = request.employment.monthly_income or 0.0
    payments = request.employment.payments_per_year or 0
    gross_income = monthly_income * payments
    expected = _employment_expectations(
        request.year,
        gross_income,
        monthly_income=monthly_income,
        payments_per_year=payments,
    )

    config = load_year_configuration(request.year)
    salary_cap = config.employment.contributions.monthly_salary_cap or 0.0
    capped_annual_income = min(gross_income, salary_cap * payments)
    expected_employee_per_payment = expected["employee_contrib"] / payments
    expected_employer_per_payment = expected["employer_contrib"] / payments

    employment_detail = result["details"][0]
    assert employment_detail["employee_contributions"] == pytest.approx(
        expected["employee_contrib"],
        rel=1e-4,
    )
    assert employment_detail["employer_contributions"] == pytest.approx(
        expected["employer_contrib"],
        rel=1e-4,
    )
    assert employment_detail["employee_contributions_per_payment"] == pytest.approx(
        expected_employee_per_payment,
        rel=1e-4,
    )
    assert employment_detail["employer_contributions_per_payment"] == pytest.approx(
        expected_employer_per_payment,
        rel=1e-4,
    )
    assert employment_detail["employer_cost"] == pytest.approx(
        expected["employer_cost"],
        rel=1e-4,
    )
    assert employment_detail["employer_cost_per_payment"] == pytest.approx(
        expected["employer_cost_per_payment"],
        rel=1e-4,
    )
    assert employment_detail["gross_income_per_payment"] == pytest.approx(
        gross_income / payments
    )
    assert employment_detail["monthly_gross_income"] == pytest.approx(monthly_income)
    assert expected["employee_contrib"] == pytest.approx(
        capped_annual_income * config.employment.contributions.employee_rate,
        rel=1e-4,
    )
    assert expected["employee_contrib"] < gross_income * config.employment.contributions.employee_rate


def test_manual_employee_contributions_respect_salary_cap() -> None:
    """Manual EFKA payments cannot increase the deductible beyond the cap."""

    request = CalculationRequest.model_validate(
        {
            "year": 2024,
            "employment": {
                "monthly_income": 1_500,
                "payments_per_year": 14,
                "employee_contributions": 500,
            },
        }
    )

    result = calculate_tax(request)

    monthly_income = request.employment.monthly_income or 0.0
    payments = request.employment.payments_per_year or 0
    gross_income = monthly_income * payments
    base_expected = _employment_expectations(
        2024,
        gross_income,
        monthly_income=monthly_income,
        payments_per_year=payments,
        manual_contributions=request.employment.employee_contributions,
    )
    expected_total_employee = base_expected["employee_contrib"]
    expected_net_income = base_expected["net_income"]
    expected_taxable_income = base_expected["taxable"]

    summary = result["summary"]
    assert summary["income_total"] == pytest.approx(gross_income)
    assert summary["taxable_income"] == pytest.approx(
        expected_taxable_income, rel=1e-4
    )
    assert summary["net_income"] == pytest.approx(expected_net_income, rel=1e-4)

    employment_detail = result["details"][0]
    assert employment_detail["employee_contributions"] == pytest.approx(
        expected_total_employee, rel=1e-4
    )
    assert "employee_contributions_manual" not in employment_detail
    assert employment_detail["net_income_per_payment"] == pytest.approx(
        expected_net_income / payments, rel=1e-4
    )
    assert employment_detail["employer_cost"] == pytest.approx(
        base_expected["employer_cost"], rel=1e-4
    )
    assert employment_detail["employer_cost_per_payment"] == pytest.approx(
        base_expected["employer_cost_per_payment"], rel=1e-4
    )


@pytest.mark.parametrize("payments_per_year", [14, 12])
def test_employment_social_contributions_can_be_excluded(
    payments_per_year: int,
) -> None:
    """Users can opt out of including EFKA contributions in the net result."""

    base_request = CalculationRequest.model_validate(
        {
            "year": 2024,
            "employment": {
                "monthly_income": 2_000,
                "payments_per_year": payments_per_year,
                "employee_contributions": 250,
            },
        }
    )

    excluded_request = CalculationRequest.model_validate(
        {
            "year": 2024,
            "employment": {
                "monthly_income": 2_000,
                "payments_per_year": payments_per_year,
                "employee_contributions": 250,
                "include_social_contributions": False,
            },
        }
    )

    inclusive_result = calculate_tax(base_request)
    excluded_result = calculate_tax(excluded_request)

    inclusive_detail = next(
        detail for detail in inclusive_result["details"] if detail["category"] == "employment"
    )
    excluded_detail = next(
        detail for detail in excluded_result["details"] if detail["category"] == "employment"
    )

    inclusive_contributions = inclusive_detail.get("employee_contributions", 0.0)
    assert inclusive_contributions > 0
    assert excluded_detail.get("employee_contributions", 0.0) == pytest.approx(0.0)
    assert excluded_detail.get("employee_contributions_manual", 0.0) == pytest.approx(0.0)
    assert excluded_detail.get("employer_contributions", 0.0) == pytest.approx(0.0)
    assert inclusive_detail["employer_cost"] == pytest.approx(
        inclusive_detail["gross_income"] + inclusive_detail["employer_contributions"],
        rel=1e-4,
    )
    assert excluded_detail["employer_cost"] == pytest.approx(
        excluded_detail["gross_income"],
        rel=1e-4,
    )
    assert inclusive_detail["employer_cost_per_payment"] == pytest.approx(
        (inclusive_detail["gross_income"] + inclusive_detail["employer_contributions"])
        / payments_per_year,
        rel=1e-4,
    )
    assert excluded_detail["employer_cost_per_payment"] == pytest.approx(
        excluded_detail["gross_income"] / payments_per_year,
        rel=1e-4,
    )

    tax_delta = excluded_detail["total_tax"] - inclusive_detail["total_tax"]
    assert excluded_detail["net_income"] == pytest.approx(
        inclusive_detail["net_income"] + inclusive_contributions - tax_delta,
        rel=1e-4,
    )

    inclusive_summary = inclusive_result["summary"]
    excluded_summary = excluded_result["summary"]

    tax_delta_summary = (
        excluded_summary["tax_total"] - inclusive_summary["tax_total"]
    )
    assert excluded_summary["net_income"] == pytest.approx(
        inclusive_summary["net_income"]
        + inclusive_contributions
        - tax_delta_summary,
        rel=1e-4,
    )


@pytest.mark.parametrize(
    "year,payments_per_year,include_social",
    [
        (2024, 14, True),
        (2024, 12, False),
        (2025, 14, True),
        (2025, 12, False),
    ],
)
def test_employment_breakdown_remains_balanced(
    year: int, payments_per_year: int, include_social: bool
) -> None:
    """Employment detail rows reconcile gross, tax, and contributions."""

    employment_payload: dict[str, Any] = {
        "gross_income": 60_000,
        "payments_per_year": payments_per_year,
        "employee_contributions": 200.0,
    }
    if not include_social:
        employment_payload["include_social_contributions"] = False

    request = CalculationRequest.model_validate(
        {
            "year": year,
            "employment": employment_payload,
        }
    )

    result = calculate_tax(request)

    employment_detail = next(
        detail for detail in result["details"] if detail["category"] == "employment"
    )

    gross_income = employment_detail["gross_income"]
    total_tax = employment_detail["total_tax"]
    net_income = employment_detail["net_income"]
    employee_contributions = employment_detail.get("employee_contributions", 0.0)

    if include_social:
        assert employee_contributions > 0
        expected_total = total_tax + net_income + employee_contributions
    else:
        assert employee_contributions == pytest.approx(0.0)
        expected_total = total_tax + net_income

    assert gross_income == pytest.approx(expected_total, rel=1e-4, abs=0.05)


def test_calculate_tax_with_freelance_income() -> None:
    """Freelance profit combines progressive tax and trade fee."""

    request = CalculationRequest.model_validate(
        {
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
    )

    result = calculate_tax(request)
    expected = _freelance_expectations(request)

    summary = result["summary"]
    assert summary["income_total"] == pytest.approx(expected["summary"]["income"])
    assert summary["taxable_income"] == pytest.approx(expected["summary"]["taxable"])
    assert summary["tax_total"] == pytest.approx(expected["summary"]["tax"])
    assert summary["net_income"] == pytest.approx(expected["summary"]["net"])
    assert summary["net_monthly_income"] == pytest.approx(
        expected["summary"]["net_monthly"],
        rel=1e-4,
    )
    assert summary["average_monthly_tax"] == pytest.approx(
        expected["summary"]["avg_monthly_tax"],
        rel=1e-4,
    )
    assert summary["effective_tax_rate"] == pytest.approx(
        expected["summary"]["effective_rate"],
        rel=1e-4,
    )

    details_by_category = {
        detail["category"]: detail for detail in result["details"]
    }
    expected_categories = {"employment", "freelance"}
    assert set(details_by_category) == expected_categories

    employment_detail = details_by_category["employment"]
    assert employment_detail["gross_income"] == pytest.approx(
        expected["employment"]["gross"]
    )
    assert employment_detail["tax_before_credits"] == pytest.approx(
        expected["employment"]["tax_before_credit"],
        rel=1e-4,
    )
    assert employment_detail["credits"] == pytest.approx(
        expected["employment"]["credit"],
        rel=1e-4,
    )
    assert employment_detail["total_tax"] == pytest.approx(
        expected["employment"]["tax"],
        rel=1e-4,
    )
    assert employment_detail["employee_contributions"] == pytest.approx(
        expected["employment"]["employee_contrib"],
        rel=1e-4,
    )
    assert employment_detail["employer_contributions"] == pytest.approx(
        expected["employment"]["employer_contrib"],
        rel=1e-4,
    )
    assert employment_detail["employer_cost"] == pytest.approx(
        expected["employment"]["gross"] + expected["employment"]["employer_contrib"],
        rel=1e-4,
    )

    freelance_detail = details_by_category["freelance"]
    assert freelance_detail["gross_income"] == pytest.approx(
        expected["freelance"]["gross"]
    )
    assert freelance_detail["taxable_income"] == pytest.approx(
        expected["freelance"]["taxable"],
        rel=1e-4,
    )
    assert freelance_detail["tax"] == pytest.approx(
        expected["freelance"]["tax"],
        rel=1e-4,
    )
    assert freelance_detail["trade_fee"] == pytest.approx(0.0)
    assert freelance_detail["total_tax"] == pytest.approx(
        expected["freelance"]["tax"],
        rel=1e-4,
    )
    assert freelance_detail["net_income"] == pytest.approx(
        expected["freelance"]["net"],
        rel=1e-4,
    )
    assert freelance_detail["credits"] == pytest.approx(
        expected["freelance"]["credit"],
        rel=1e-4,
    )
    assert freelance_detail["deductible_contributions"] == pytest.approx(
        expected["freelance"]["contributions"]
    )


@pytest.mark.parametrize(
    ("toggle_field", "detail_field"),
    [
        ("include_category_contributions", "category_contributions"),
        ("include_mandatory_contributions", "additional_contributions"),
        ("include_auxiliary_contributions", "auxiliary_contributions"),
        ("include_lump_sum_contributions", "lump_sum_contributions"),
    ],
)
def test_freelance_contribution_toggle_excludes_amount(
    toggle_field: str, detail_field: str
) -> None:
    """Disabling a freelance contribution removes it from the taxable offsets."""

    base_payload = {
        "year": 2024,
        "employment": {"gross_income": 15_000},
        "freelance": {
            "gross_revenue": 40_000,
            "deductible_expenses": 10_000,
            "mandatory_contributions": 2_000,
            "auxiliary_contributions": 1_200,
            "lump_sum_contributions": 600,
            "efka_category": "general_class_1",
            "include_trade_fee": False,
        },
    }

    base_request = CalculationRequest.model_validate(base_payload)
    base_result = calculate_tax(base_request)
    base_detail = next(
        detail for detail in base_result["details"] if detail["category"] == "freelance"
    )

    removed_amount = base_detail.get(detail_field, 0.0)
    assert removed_amount > 0

    toggled_payload = deepcopy(base_payload)
    toggled_payload["freelance"][toggle_field] = False
    toggled_request = CalculationRequest.model_validate(toggled_payload)
    toggled_result = calculate_tax(toggled_request)
    toggled_detail = next(
        detail for detail in toggled_result["details"] if detail["category"] == "freelance"
    )

    assert toggled_detail.get(detail_field, 0.0) == pytest.approx(0.0)

    taxable_delta = (
        toggled_detail["taxable_income"] - base_detail["taxable_income"]
    )
    assert taxable_delta == pytest.approx(removed_amount, abs=0.05, rel=1e-4)

    deductible_delta = (
        base_detail["deductible_contributions"]
        - toggled_detail["deductible_contributions"]
    )
    assert deductible_delta == pytest.approx(removed_amount, abs=0.05, rel=1e-4)


def test_freelance_contribution_toggle_combination() -> None:
    """Multiple contribution toggles combine to raise taxable income proportionally."""

    base_payload = {
        "year": 2024,
        "employment": {"gross_income": 15_000},
        "freelance": {
            "gross_revenue": 40_000,
            "deductible_expenses": 10_000,
            "mandatory_contributions": 2_000,
            "auxiliary_contributions": 1_200,
            "lump_sum_contributions": 600,
            "efka_category": "general_class_1",
            "include_trade_fee": False,
        },
    }

    base_detail = next(
        detail
        for detail in calculate_tax(CalculationRequest.model_validate(base_payload))["details"]
        if detail["category"] == "freelance"
    )

    combined_payload = deepcopy(base_payload)
    combined_payload["freelance"].update(
        {
            "include_category_contributions": False,
            "include_auxiliary_contributions": False,
        }
    )

    combined_detail = next(
        detail
        for detail in calculate_tax(
            CalculationRequest.model_validate(combined_payload)
        )["details"]
        if detail["category"] == "freelance"
    )

    category_amount = base_detail.get("category_contributions", 0.0)
    auxiliary_amount = base_detail.get("auxiliary_contributions", 0.0)
    assert category_amount > 0
    assert auxiliary_amount > 0

    expected_removed = category_amount + auxiliary_amount

    assert combined_detail.get("category_contributions", 0.0) == pytest.approx(0.0)
    assert combined_detail.get("auxiliary_contributions", 0.0) == pytest.approx(0.0)
    # Unaffected contributions remain present.
    assert combined_detail.get("additional_contributions", 0.0) == pytest.approx(
        base_detail.get("additional_contributions", 0.0), rel=1e-4
    )
    assert combined_detail.get("lump_sum_contributions", 0.0) == pytest.approx(
        base_detail.get("lump_sum_contributions", 0.0), rel=1e-4
    )

    taxable_delta = combined_detail["taxable_income"] - base_detail["taxable_income"]
    assert taxable_delta == pytest.approx(expected_removed, abs=0.05, rel=1e-4)

    deductible_delta = (
        base_detail["deductible_contributions"]
        - combined_detail["deductible_contributions"]
    )
    assert deductible_delta == pytest.approx(expected_removed, abs=0.05, rel=1e-4)

def test_calculate_tax_respects_locale_toggle() -> None:
    """Locale toggle switches translation catalogue."""

    request = CalculationRequest.model_validate(
        {"year": 2024, "locale": "el", "employment": {"gross_income": 10_000}}
    )

    result = calculate_tax(request)

    assert result["meta"]["locale"] == "el"
    assert result["details"][0]["label"] == "Εισόδημα μισθωτών"
    assert result["summary"]["labels"]["income_total"] == "Συνολικό εισόδημα"


def test_youth_relief_applies_when_toggle_and_age_match() -> None:
    """Employment youth relief applies reduced bracket rates when confirmed."""

    base_payload = {
        "year": 2026,
        "dependents": {"children": 0},
        "employment": {"gross_income": 20_000},
        "demographics": {"taxpayer_birth_year": 2003},
    }

    youth_request = CalculationRequest.model_validate(
        {**base_payload, "toggles": {"youth_eligibility": True}}
    )
    youth_result = calculate_tax(youth_request)

    employment_detail = next(
        detail for detail in youth_result["details"] if detail["category"] == "employment"
    )

    # Gross income less statutory employee contributions defines the taxable base.
    expected_employee_contrib = employment_detail["employee_contributions"]
    taxable_income = base_payload["employment"]["gross_income"] - expected_employee_contrib
    assert employment_detail["taxable_income"] == pytest.approx(taxable_income)

    # Youth bracket rates: zero tax on the first €20k for confirmed relief.
    expected_tax_before_credit = 0.0

    assert employment_detail["tax_before_credits"] == pytest.approx(
        expected_tax_before_credit, rel=1e-4
    )

    baseline_request = CalculationRequest.model_validate(
        {**base_payload, "toggles": {"youth_eligibility": False}}
    )
    baseline_result = calculate_tax(baseline_request)
    baseline_detail = next(
        detail for detail in baseline_result["details"] if detail["category"] == "employment"
    )

    # Household rates without youth relief: 10k at 9%, remainder at 20% until 20k.
    first_band = min(taxable_income, 10_000)
    second_band = max(min(taxable_income - first_band, 10_000), 0)
    expected_baseline_tax = first_band * 0.09 + second_band * 0.20
    remaining_baseline = taxable_income - (first_band + second_band)
    if remaining_baseline > 0:
        expected_baseline_tax += remaining_baseline * 0.26

    assert baseline_detail["tax_before_credits"] == pytest.approx(
        expected_baseline_tax, rel=1e-4
    )
    assert baseline_detail["tax_before_credits"] > employment_detail["tax_before_credits"]


def test_2026_youth_relief_second_band_matches_announced_rates() -> None:
    """Youth relief for ages 26-30 limits the second band to 9%."""

    base_payload = {
        "year": 2026,
        "dependents": {"children": 0},
        "employment": {
            "gross_income": 20_000,
            "include_social_contributions": False,
        },
        "demographics": {"taxpayer_birth_year": 1999},
    }

    youth_request = CalculationRequest.model_validate(
        {**base_payload, "toggles": {"youth_eligibility": True}}
    )
    youth_result = calculate_tax(youth_request)
    youth_detail = next(
        detail for detail in youth_result["details"] if detail["category"] == "employment"
    )

    assert youth_detail["taxable_income"] == pytest.approx(20_000)
    assert youth_detail["tax_before_credits"] == pytest.approx(1_800, rel=1e-4)

    baseline_request = CalculationRequest.model_validate(
        {**base_payload, "toggles": {"youth_eligibility": False}}
    )
    baseline_result = calculate_tax(baseline_request)
    baseline_detail = next(
        detail for detail in baseline_result["details"] if detail["category"] == "employment"
    )

    assert baseline_detail["taxable_income"] == pytest.approx(20_000)
    assert baseline_detail["tax_before_credits"] == pytest.approx(2_900, rel=1e-4)
    assert youth_detail["tax_before_credits"] < baseline_detail["tax_before_credits"]


def test_2026_under_25_dependant_rates_match_announced_scale() -> None:
    """Dependants adjust youth relief brackets according to the 2026 scale."""

    base_payload = {
        "year": 2026,
        "dependents": {"children": 2},
        "employment": {
            "gross_income": 30_000,
            "include_social_contributions": False,
        },
        "demographics": {"taxpayer_birth_year": 2004},
    }

    youth_request = CalculationRequest.model_validate(
        {**base_payload, "toggles": {"youth_eligibility": True}}
    )
    youth_result = calculate_tax(youth_request)
    youth_detail = next(
        detail for detail in youth_result["details"] if detail["category"] == "employment"
    )

    assert youth_detail["taxable_income"] == pytest.approx(30_000)
    assert youth_detail["tax_before_credits"] == pytest.approx(2_200, rel=1e-4)

    baseline_request = CalculationRequest.model_validate(
        {**base_payload, "toggles": {"youth_eligibility": False}}
    )
    baseline_result = calculate_tax(baseline_request)
    baseline_detail = next(
        detail for detail in baseline_result["details"] if detail["category"] == "employment"
    )

    assert baseline_detail["tax_before_credits"] == pytest.approx(4_700, rel=1e-4)
    assert youth_detail["tax_before_credits"] < baseline_detail["tax_before_credits"]


def test_calculate_tax_combines_employment_and_pension_credit() -> None:
    """Salary and pension income share a single tax credit."""

    request = CalculationRequest.model_validate(
        {
            "year": 2024,
            "dependents": {"children": 1},
            "employment": {"gross_income": 10_000},
            "pension": {"gross_income": 10_000},
        }
    )

    result = calculate_tax(request)

    assert result["summary"]["tax_total"] == pytest.approx(2_144.86, rel=1e-4)
    assert result["summary"]["taxable_income"] == pytest.approx(18_613.0)
    assert result["summary"]["net_income"] == pytest.approx(16_468.14, rel=1e-4)

    employment_detail = next(
        detail for detail in result["details"] if detail["category"] == "employment"
    )
    pension_detail = next(
        detail for detail in result["details"] if detail["category"] == "pension"
    )

    assert employment_detail["tax_before_credits"] == pytest.approx(1_293.3, rel=1e-4)
    assert pension_detail["tax_before_credits"] == pytest.approx(1_501.56, rel=1e-4)

    assert employment_detail["credits"] == pytest.approx(300.78, rel=1e-4)
    assert pension_detail["credits"] == pytest.approx(349.22, rel=1e-4)

    assert employment_detail["total_tax"] == pytest.approx(992.51, rel=1e-4)
    assert pension_detail["total_tax"] == pytest.approx(1_152.35, rel=1e-4)
    assert employment_detail["employee_contributions"] == pytest.approx(1_387.0)


def test_calculate_tax_with_pension_and_rental_income() -> None:
    request = CalculationRequest.model_validate(
        {
            "year": 2024,
            "dependents": {"children": 2},
            "pension": {"gross_income": 18_000},
            "rental": {"gross_income": 15_000, "deductible_expenses": 2_000},
        }
    )

    result = calculate_tax(request)

    pension_detail = next(
        detail for detail in result["details"] if detail["category"] == "pension"
    )
    rental_detail = next(
        detail for detail in result["details"] if detail["category"] == "rental"
    )

    # Pension tax: (10k * 9%) + (8k * 22%) = 900 + 1760 = 2,660
    # Credit for 2 children = 900 reduced by €120 above the threshold -> tax 1,880
    assert pension_detail["total_tax"] == pytest.approx(1_880.0)

    # Rental taxable: 15k - 2k = 13k -> 12k @15% + 1k @35% = 2,150
    assert rental_detail["taxable_income"] == pytest.approx(13_000.0)
    assert rental_detail["total_tax"] == pytest.approx(2_150.0)
    assert rental_detail["net_income"] == pytest.approx(10_850.0)

    assert result["summary"]["income_total"] == pytest.approx(33_000.0)
    assert result["summary"]["taxable_income"] == pytest.approx(31_000.0)
    assert result["summary"]["tax_total"] == pytest.approx(4_030.0)


def test_calculate_tax_with_investment_income_breakdown() -> None:
    request = CalculationRequest.model_validate(
        {
            "year": 2024,
            "investment": {
                "dividends": 1_000,
                "interest": 500,
                "capital_gains": 2_000,
            },
        }
    )

    result = calculate_tax(request)

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
    request = CalculationRequest.model_validate(
        {
            "year": 2024,
            "obligations": {"enfia": 320, "luxury": 880},
        }
    )

    result = calculate_tax(request)

    summary = result["summary"]
    assert summary["income_total"] == 0.0
    assert summary["taxable_income"] == 0.0
    assert summary["tax_total"] == pytest.approx(1_200.0)
    assert summary["net_income"] == pytest.approx(-1_200.0)

    details = {detail["category"]: detail for detail in result["details"]}
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

    request_2024 = CalculationRequest.model_validate({"year": 2024, **base_payload})
    request_2025 = CalculationRequest.model_validate({"year": 2025, **base_payload})
    request_2026 = CalculationRequest.model_validate({"year": 2026, **base_payload})

    result_2024 = calculate_tax(request_2024)
    result_2025 = calculate_tax(request_2025)
    result_2026 = calculate_tax(request_2026)

    expected_2024 = _employment_expectations(2024, 25_000, children=2)
    expected_2025 = _employment_expectations(2025, 25_000, children=2)
    expected_2026 = _employment_expectations(2026, 25_000, children=2)

    assert result_2024["summary"]["tax_total"] == pytest.approx(
        expected_2024["tax"], rel=1e-4
    )
    assert result_2025["summary"]["tax_total"] == pytest.approx(
        expected_2025["tax"], rel=1e-4
    )
    assert result_2026["summary"]["tax_total"] == pytest.approx(
        expected_2026["tax"], rel=1e-4
    )

    assert expected_2025["credit"] > expected_2024["credit"]
    assert expected_2026["credit"] >= expected_2025["credit"]
    assert result_2026["meta"]["year"] == request_2026.year


def test_2026_presumptive_relief_defaults_apply() -> None:
    """Config defaults apply presumptive relief flags when none are provided."""

    payload = {"year": 2026}

    result = calculate_tax(payload)

    assert result["meta"]["presumptive_adjustments"] == [
        "small_village",
        "new_mother",
    ]


def test_2026_presumptive_relief_can_be_overridden_by_request() -> None:
    """Explicit demographics suppress presumptive adjustments even with active toggles."""

    payload = {
        "year": 2026,
        "demographics": {"small_village": False, "new_mother": False},
    }

    result = calculate_tax(payload)

    assert "presumptive_adjustments" not in result["meta"]


def test_2026_presumptive_relief_partial_and_toggle_control() -> None:
    """Single adjustments are reported unless the tekmiria reduction toggle disables them."""

    single_adjustment_payload = {
        "year": 2026,
        "demographics": {"small_village": True, "new_mother": False},
    }

    single_adjustment_result = calculate_tax(single_adjustment_payload)

    assert single_adjustment_result["meta"]["presumptive_adjustments"] == [
        "small_village"
    ]

    gated_payload = {
        "year": 2026,
        "demographics": {"small_village": True, "new_mother": False},
        "toggles": {"tekmiria_reduction": False},
    }

    gated_result = calculate_tax(gated_payload)

    assert "presumptive_adjustments" not in gated_result["meta"]


def test_2026_dependant_credit_tiers_are_pending_confirmation() -> None:
    """Dependent credit tiers for 2026 are provisional but expose concrete amounts."""

    config = load_year_configuration(2026)
    credit = config.employment.tax_credit

    assert credit.pending_confirmation is True
    assert credit.incremental_amount_per_child == pytest.approx(230.0)
    assert credit.amount_for_children(0) == pytest.approx(778.0)
    assert credit.amount_for_children(1) == pytest.approx(820.0)
    assert credit.amount_for_children(2) == pytest.approx(910.0)
    assert credit.amount_for_children(3) == pytest.approx(1_140.0)
    # Additional children continue the incremental increase.
    assert credit.amount_for_children(5) == pytest.approx(1_600.0)


def test_2026_rental_mid_band_cut() -> None:
    """Rental income applies the reduced mid-band threshold introduced for 2026."""

    request = CalculationRequest.model_validate(
        {
            "year": 2026,
            "rental": {"gross_income": 28_000, "deductible_expenses": 2_000},
        }
    )

    result = calculate_tax(request)
    rental_detail = next(
        detail for detail in result["details"] if detail["category"] == "rental"
    )

    taxable_income = 26_000.0
    expected_tax = (12_000 * 0.15) + (12_000 * 0.25) + (2_000 * 0.35)

    assert rental_detail["taxable_income"] == pytest.approx(taxable_income)
    assert rental_detail["total_tax"] == pytest.approx(expected_tax)
    assert result["summary"]["tax_total"] == pytest.approx(expected_tax)


def test_2026_efka_categories_marked_as_estimates() -> None:
    """All 2026 EFKA categories surface the provisional estimate flag."""

    config = load_year_configuration(2026)
    categories = config.freelance.efka_categories

    assert categories, "Expected EFKA categories for 2026"
    assert all(category.estimate for category in categories)


def test_calculate_tax_with_freelance_category_contributions() -> None:
    """EFKA category metadata populates contribution breakdowns."""

    config = load_year_configuration(2024)
    category = next(
        entry
        for entry in config.freelance.efka_categories
        if entry.id == "general_class_1"
    )
    expected_category_contribution = category.monthly_amount * 6
    expected_deductible = expected_category_contribution + 500 + 120

    request = CalculationRequest.model_validate(
        {
            "year": 2024,
            "freelance": {
                "profit": 30_000,
                "efka_category": "general_class_1",
                "efka_months": 6,
                "mandatory_contributions": 500,
                "auxiliary_contributions": 120,
            },
        }
    )

    result = calculate_tax(request)

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
        entry
        for entry in config.freelance.efka_categories
        if entry.id == "engineer_class_1"
    )
    months = 12
    auxiliary_total = (category.auxiliary_monthly_amount or 0) * months
    lump_sum_total = (category.lump_sum_monthly_amount or 0) * months

    request = CalculationRequest.model_validate(
        {
            "year": 2024,
            "freelance": {
                "profit": 40_000,
                "efka_category": "engineer_class_1",
                "efka_months": months,
                "auxiliary_contributions": auxiliary_total,
                "lump_sum_contributions": lump_sum_total,
            },
        }
    )

    result = calculate_tax(request)
    freelance_detail = result["details"][0]

    expected_category = category.monthly_amount * months
    expected_total = expected_category + auxiliary_total + lump_sum_total

    assert freelance_detail["category_contributions"] == pytest.approx(
        expected_category
    )
    assert freelance_detail["auxiliary_contributions"] == pytest.approx(auxiliary_total)
    assert freelance_detail["lump_sum_contributions"] == pytest.approx(lump_sum_total)
    assert freelance_detail["deductible_contributions"] == pytest.approx(expected_total)


def test_calculate_tax_applies_deductions_across_components() -> None:
    """Itemised deductions now translate into capped tax credits."""

    config = load_year_configuration(2024)
    rules = config.deductions.rules

    request = CalculationRequest.model_validate(
        {
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
    )

    employment_income = request.employment.gross_income
    income_cap_rate = rules.donations.income_cap_rate
    income_cap = (
        employment_income * income_cap_rate if income_cap_rate is not None else None
    )
    eligible_donations = (
        min(request.deductions.donations, income_cap)
        if income_cap is not None
        else request.deductions.donations
    )
    expected_donation_credit = eligible_donations * rules.donations.credit_rate
    expected_education_credit = (
        min(request.deductions.education, rules.education.max_eligible_expense)
        * rules.education.credit_rate
    )
    expected_insurance_credit = (
        min(request.deductions.insurance, rules.insurance.max_eligible_expense)
        * rules.insurance.credit_rate
    )
    expected_total_credit = (
        expected_donation_credit + expected_education_credit + expected_insurance_credit
    )

    result = calculate_tax(request)

    employment_expected = _employment_expectations(
        request.year,
        employment_income,
    )

    employment_detail = next(
        detail for detail in result["details"] if detail["category"] == "employment"
    )
    agricultural_detail = next(
        detail for detail in result["details"] if detail["category"] == "agricultural"
    )

    assert employment_detail["deductions_applied"] == pytest.approx(
        expected_total_credit
    )
    assert employment_detail["taxable_income"] == pytest.approx(
        employment_expected["taxable"]
    )
    assert "deductions_applied" not in agricultural_detail
    assert agricultural_detail["taxable_income"] == pytest.approx(10_000.0)

    summary = result["summary"]
    assert summary["deductions_entered"] == pytest.approx(5_000.0)
    assert summary["deductions_applied"] == pytest.approx(expected_total_credit)

    breakdown = summary.get("deductions_breakdown")
    assert breakdown is not None
    donations = next(item for item in breakdown if item["type"] == "donations")
    assert donations["credit_rate"] == pytest.approx(rules.donations.credit_rate)
    assert donations["credit_applied"] == pytest.approx(expected_donation_credit)
    medical = next(item for item in breakdown if item["type"] == "medical")
    assert medical["credit_applied"] == pytest.approx(0.0)


def test_calculate_tax_applies_donation_credit_to_freelance_tax() -> None:
    """Donation credits now reduce freelance progressive tax directly."""

    config = load_year_configuration(2024)
    donation_rules = config.deductions.rules.donations

    base_request = CalculationRequest.model_validate(
        {
            "year": 2024,
            "freelance": {"profit": 20_000},
        }
    )

    baseline = calculate_tax(base_request)
    with_donation = calculate_tax(
        base_request.model_copy(update={"deductions": {"donations": 100}})
    )

    baseline_tax = baseline["summary"]["tax_total"]
    donation_tax = with_donation["summary"]["tax_total"]

    expected_credit = 100 * donation_rules.credit_rate
    assert baseline_tax - donation_tax == pytest.approx(expected_credit)

    breakdown = with_donation["summary"].get("deductions_breakdown")
    assert breakdown is not None
    donation_entry = next(item for item in breakdown if item["type"] == "donations")
    assert donation_entry["credit_rate"] == pytest.approx(
        donation_rules.credit_rate
    )
    assert donation_entry["credit_applied"] == pytest.approx(expected_credit)


def test_calculate_tax_applies_medical_credit_threshold_for_freelance() -> None:
    """Medical credits apply the 5% threshold before reducing tax."""

    config = load_year_configuration(2024)
    medical_rules = config.deductions.rules.medical

    base_request = CalculationRequest.model_validate(
        {
            "year": 2024,
            "freelance": {"profit": 20_000},
        }
    )

    baseline = calculate_tax(base_request)
    with_medical = calculate_tax(
        base_request.model_copy(update={"deductions": {"medical": 2_500}})
    )

    baseline_tax = baseline["summary"]["tax_total"]
    medical_tax = with_medical["summary"]["tax_total"]

    taxable_income = base_request.freelance.profit
    threshold = taxable_income * medical_rules.income_threshold_rate
    eligible_expense = max(2_500 - threshold, 0.0)
    expected_credit = min(
        eligible_expense * medical_rules.credit_rate, medical_rules.max_credit
    )

    assert baseline_tax - medical_tax == pytest.approx(expected_credit)

    breakdown = with_medical["summary"].get("deductions_breakdown")
    assert breakdown is not None
    medical_entry = next(item for item in breakdown if item["type"] == "medical")
    assert medical_entry["eligible"] == pytest.approx(eligible_expense)
    assert medical_entry["credit_rate"] == pytest.approx(medical_rules.credit_rate)
    assert medical_entry["credit_applied"] == pytest.approx(expected_credit)


def test_calculate_tax_trade_fee_auto_exemption_by_year() -> None:
    """Trade fee remains waived from 2024 onwards once the abolition takes effect."""

    request_2024 = CalculationRequest.model_validate(
        {"year": 2024, "freelance": {"profit": 12_000}}
    )
    result_2024 = calculate_tax(request_2024)
    freelance_2024 = next(
        detail for detail in result_2024["details"] if detail["category"] == "freelance"
    )
    assert freelance_2024["trade_fee"] == pytest.approx(0.0)

    request_2025 = CalculationRequest.model_validate(
        {"year": 2025, "freelance": {"profit": 12_000}}
    )
    result_2025 = calculate_tax(request_2025)
    freelance_2025 = next(
        detail for detail in result_2025["details"] if detail["category"] == "freelance"
    )
    assert freelance_2025["trade_fee"] == pytest.approx(0.0)

    assert result_2025["summary"]["tax_total"] == pytest.approx(
        result_2024["summary"]["tax_total"]
    )


def test_calculate_tax_with_agricultural_and_other_income() -> None:
    """Agricultural and other income categories produce dedicated details."""

    request = CalculationRequest.model_validate(
        {
            "year": 2024,
            "agricultural": {"gross_revenue": 15_000, "deductible_expenses": 2_000},
            "other": {"taxable_income": 5_000},
        }
    )

    result = calculate_tax(request)

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
    assert summary["taxable_income"] == pytest.approx(18_000.0)
    assert summary["tax_total"] == pytest.approx(2_660.0)


def test_agricultural_only_income_receives_tax_credit() -> None:
    """Sole agricultural income qualifies for the base tax credit in 2025."""

    config = load_year_configuration(2025)
    base_credit = config.employment.tax_credit.amount_for_children(0)

    request = CalculationRequest.model_validate(
        {
            "year": 2025,
            "agricultural": {
                "gross_revenue": 12_000,
                "deductible_expenses": 2_000,
            },
        }
    )

    result = calculate_tax(request)

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

    request = CalculationRequest.model_validate(
        {
            "year": 2025,
            "dependents": {"children": 2},
            "agricultural": {
                "gross_revenue": 28_000,
                "deductible_expenses": 3_000,
                "professional_farmer": True,
            },
            "other": {"taxable_income": 4_000},
        }
    )

    result = calculate_tax(request)

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

    config = load_year_configuration(2025)
    trade_fee_config = config.freelance.trade_fee

    base_request = CalculationRequest.model_validate(
        {
            "year": 2025,
            "freelance": {
                "profit": 12_000,
                "efka_category": "general_class_1",
                "trade_fee_location": "standard",
                "years_active": 2,
                "newly_self_employed": True,
            },
        }
    )

    reduced_fee_result = calculate_tax(base_request)
    reduced_detail = reduced_fee_result["details"][0]
    assert reduced_detail["trade_fee"] == pytest.approx(
        trade_fee_config.reduced_amount or trade_fee_config.standard_amount
    )

    no_fee_request = base_request.model_copy(
        update={
            "freelance": base_request.freelance.model_copy(
                update={"include_trade_fee": False}
            )
        }
    )
    no_fee_result = calculate_tax(no_fee_request)
    no_fee_detail = no_fee_result["details"][0]
    assert no_fee_detail["trade_fee"] == pytest.approx(0.0)
    expected_difference = reduced_detail["trade_fee"]
    assert reduced_detail["total_tax"] == pytest.approx(
        no_fee_detail["total_tax"] + expected_difference
    )
