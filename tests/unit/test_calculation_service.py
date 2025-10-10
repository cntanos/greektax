"""Unit tests for the calculation service."""
from __future__ import annotations

from copy import deepcopy
from types import MappingProxyType
from typing import Any

import pytest
from pydantic import ValidationError

from greektax.backend.app.models import (
    NET_INCOME_INPUT_ERROR,
    CalculationRequest,
    DeductionBreakdownEntry,
    DetailEntry,
    ResponseMeta,
    Summary,
    SummaryLabels,
)
from greektax.backend.services.calculation_service import (
    _RESPONSE_VALIDATION_ENV,
    CalculationResponse,
    _construct_response_model,
    _normalise_additional_income,
    _normalise_employment,
    _normalise_freelance,
    _normalise_pension,
    _validate_birth_year_guard,
    calculate_tax,
)
from greektax.backend.config.year_config import (
    TaxBracket,
    YearConfiguration,
    load_year_configuration,
)

DEFAULT_DEMOGRAPHICS = {"birth_year": 1990}


def build_request(payload: dict[str, Any]) -> CalculationRequest:
    data = deepcopy(payload)
    demographics = data.setdefault("demographics", {})
    if "birth_year" not in demographics:
        alias_year = demographics.get("taxpayer_birth_year")
        if alias_year is None:
            alias_year = DEFAULT_DEMOGRAPHICS["birth_year"]
        demographics["birth_year"] = alias_year
    return CalculationRequest.model_validate(data)


def test_normalise_employment_prefers_monthly_income_defaults() -> None:
    config = load_year_configuration(2024)
    request = build_request(
        {
            "year": 2024,
            "employment": {
                "monthly_income": 1_200.0,
                "employee_contributions": 150.0,
            },
        }
    )

    employment = _normalise_employment(request, config)

    default_payments = config.employment.payroll.default_payments_per_year
    assert employment.payments_per_year == default_payments
    assert employment.monthly_income == 1_200.0
    assert employment.income == pytest.approx(1_200.0 * default_payments)
    assert employment.manual_contributions == 150.0
    assert employment.declared_gross_income == request.employment.gross_income


def test_normalise_employment_uses_declared_gross_income() -> None:
    config = load_year_configuration(2024)
    payments_choice = next(
        iter(config.employment.payroll.allowed_payments_per_year)
    )
    request = build_request(
        {
            "year": 2024,
            "employment": {
                "gross_income": 24_000.0,
                "monthly_income": 1_000.0,
                "payments_per_year": payments_choice,
            },
        }
    )

    employment = _normalise_employment(request, config)

    assert employment.income == 24_000.0
    assert employment.payments_per_year == payments_choice
    # Explicit monthly input should be preserved when gross income overrides
    assert employment.monthly_income == 1_000.0


def test_normalise_pension_matches_employment_behaviour() -> None:
    config = load_year_configuration(2024)
    request = build_request(
        {
            "year": 2024,
            "pension": {
                "monthly_income": 900.0,
            },
        }
    )

    pension = _normalise_pension(request, config)

    default_payments = config.pension.payroll.default_payments_per_year
    assert pension.payments_per_year == default_payments
    assert pension.income == pytest.approx(900.0 * default_payments)
    assert pension.monthly_income == 900.0


def test_normalise_freelance_derives_profit_and_contributions() -> None:
    config = load_year_configuration(2024)
    category = config.freelance.efka_categories[0]
    request = build_request(
        {
            "year": 2024,
            "freelance": {
                "gross_revenue": 12_000.0,
                "deductible_expenses": 3_000.0,
                "efka_category": category.id,
                "efka_months": None,
                "include_category_contributions": True,
                "mandatory_contributions": 200.0,
                "auxiliary_contributions": 50.0,
                "lump_sum_contributions": 25.0,
            },
        }
    )

    freelance = _normalise_freelance(request, config)

    assert freelance.profit == pytest.approx(9_000.0)
    assert freelance.category_id == category.id
    assert freelance.category_months == 12
    assert freelance.category_contribution == pytest.approx(
        category.monthly_amount * 12
    )
    assert freelance.additional_contributions == 200.0
    assert freelance.auxiliary_contributions == 50.0
    assert freelance.lump_sum_contributions == 25.0


def test_normalise_freelance_rejects_unknown_category() -> None:
    config = load_year_configuration(2024)
    request = build_request(
        {
            "year": 2024,
            "freelance": {
                "efka_category": "unknown",
            },
        }
    )

    with pytest.raises(ValueError, match="Unknown EFKA category selection"):
        _normalise_freelance(request, config)


def test_normalise_additional_income_wraps_mappings() -> None:
    request = build_request(
        {
            "year": 2024,
            "rental": {
                "gross_income": 5_000.0,
                "deductible_expenses": 500.0,
            },
            "investment": {"stocks": 1_000.0, "bonds": 0.0},
            "agricultural": {
                "gross_revenue": 2_500.0,
                "deductible_expenses": 250.0,
                "professional_farmer": True,
            },
            "other": {"taxable_income": 750.0},
        }
    )

    additional = _normalise_additional_income(request)

    assert additional.rental_gross_income == 5_000.0
    assert additional.rental_deductible_expenses == 500.0
    assert dict(additional.investment_amounts) == {"stocks": 1_000.0, "bonds": 0.0}
    with pytest.raises(TypeError):
        additional.investment_amounts["stocks"] = 0.0  # type: ignore[index]
    assert additional.agricultural_gross_revenue == 2_500.0
    assert additional.agricultural_deductible_expenses == 250.0
    assert additional.agricultural_professional_farmer is True
    assert additional.other_taxable_income == 750.0


def test_validate_birth_year_guard_blocks_income_payloads() -> None:
    config = load_year_configuration(2025)
    request = build_request(
        {
            "year": 2025,
            "demographics": {"birth_year": 2026},
            "employment": {"gross_income": 10_000.0},
            "investment": {"interest": 100.0},
        }
    )

    employment = _normalise_employment(request, config)
    pension = _normalise_pension(request, config)
    freelance = _normalise_freelance(request, config)
    additional = _normalise_additional_income(request)

    with pytest.raises(ValueError, match="birth_year must be 2025 or earlier"):
        _validate_birth_year_guard(
            request.demographics.birth_year,
            request.year,
            (
                employment.income,
                pension.income,
                freelance.profit,
                additional.rental_gross_income,
                additional.agricultural_gross_revenue,
                additional.other_taxable_income,
                *additional.investment_amounts.values(),
            ),
        )


def test_validate_birth_year_guard_allows_no_income() -> None:
    config = load_year_configuration(2026)
    request = build_request(
        {
            "year": 2026,
            "demographics": {"birth_year": 2026},
        }
    )

    employment = _normalise_employment(request, config)
    pension = _normalise_pension(request, config)
    freelance = _normalise_freelance(request, config)
    additional = _normalise_additional_income(request)

    # Should not raise
    _validate_birth_year_guard(
        request.demographics.birth_year,
        request.year,
        (
            employment.income,
            pension.income,
            freelance.profit,
            additional.rental_gross_income,
            additional.agricultural_gross_revenue,
            additional.other_taxable_income,
            *additional.investment_amounts.values(),
        ),
    )


def _summary_payload_template() -> dict[str, Any]:
    labels = {
        "income_total": "Total income",
        "taxable_income": "Taxable income",
        "tax_total": "Total tax",
        "net_income": "Net income",
        "net_monthly_income": "Net monthly income",
        "average_monthly_tax": "Average monthly tax",
        "effective_tax_rate": "Effective tax rate",
        "deductions_entered": "Deductions entered",
        "deductions_applied": "Deductions applied",
        "withholding_tax": "Withholding tax",
        "balance_due": "Balance due",
    }

    breakdown = [
        {
            "type": "charity",
            "label": "Charitable donations",
            "entered": 150.0,
            "eligible": 120.0,
            "credit_rate": 0.1,
            "credit_requested": 12.0,
            "credit_applied": 10.0,
        },
        {
            "type": "medical",
            "label": "Medical expenses",
            "entered": 200.0,
            "eligible": 180.0,
            "credit_rate": 0.05,
            "credit_requested": 9.0,
            "credit_applied": 9.0,
            "notes": "Limited relief",
        },
    ]

    return {
        "income_total": 1_200.0,
        "taxable_income": 1_000.0,
        "tax_total": 220.0,
        "net_income": 980.0,
        "net_monthly_income": 81.6666666667,
        "average_monthly_tax": 18.3333333333,
        "effective_tax_rate": 0.22,
        "deductions_entered": 150.0,
        "deductions_applied": 130.0,
        "labels": labels,
        "withholding_tax": 180.0,
        "balance_due": 40.0,
        "balance_due_is_refund": False,
        "deductions_breakdown": breakdown,
    }


def _details_payload_template() -> list[dict[str, Any]]:
    return [
        {"category": "income", "label": "Employment", "amount": 1_200.0},
        {
            "category": "deduction",
            "label": "Charitable donations",
            "amount": -10.0,
            "notes": "Eligible",
        },
    ]


def _meta_payload_template() -> dict[str, Any]:
    return {
        "year": 2024,
        "locale": "en",
        "youth_relief_category": "standard",
    }


def _response_payload_variant(
    variant: str,
) -> tuple[Any, list[Any] | tuple[Any, ...], Any]:
    summary_payload = _summary_payload_template()
    details_payload = _details_payload_template()
    meta_payload = _meta_payload_template()

    if variant == "dicts":
        return summary_payload, details_payload, meta_payload

    if variant == "models":
        summary_model = Summary.model_validate(summary_payload)
        detail_models = [
            DetailEntry.model_validate(entry) for entry in details_payload
        ]
        meta_model = ResponseMeta.model_validate(meta_payload)
        return summary_model, detail_models, meta_model

    if variant == "mixed":
        summary_mixed = dict(summary_payload)
        summary_mixed["labels"] = SummaryLabels.model_validate(summary_payload["labels"])
        breakdown_payload = summary_payload["deductions_breakdown"]
        summary_mixed["deductions_breakdown"] = [
            DeductionBreakdownEntry.model_validate(breakdown_payload[0]),
            MappingProxyType(dict(breakdown_payload[1])),
        ]
        summary_value = MappingProxyType(summary_mixed)

        details_value = [
            DetailEntry.model_validate(details_payload[0]),
            MappingProxyType(dict(details_payload[1])),
        ]
        meta_value = ResponseMeta.model_validate(meta_payload)
        return summary_value, details_value, meta_value

    if variant == "partial":
        partial_summary = {
            key: summary_payload[key]
            for key in [
                "income_total",
                "taxable_income",
                "tax_total",
                "net_income",
                "net_monthly_income",
                "average_monthly_tax",
                "effective_tax_rate",
                "deductions_entered",
                "deductions_applied",
            ]
        }
        partial_summary["labels"] = dict(summary_payload["labels"])
        partial_summary["deductions_breakdown"] = None

        partial_details: list[Any] = [
            {"category": "income", "label": "Employment"}
        ]
        partial_meta = {"year": meta_payload["year"], "locale": meta_payload["locale"]}
        return partial_summary, partial_details, partial_meta

    raise AssertionError(f"Unknown variant: {variant}")


@pytest.mark.parametrize("variant", ["dicts", "models", "mixed", "partial"])
def test_construct_response_model_normalises_payloads(
    variant: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fast-path and validated responses should serialise identically."""

    monkeypatch.delenv(_RESPONSE_VALIDATION_ENV, raising=False)
    summary_value, details_value, meta_value = _response_payload_variant(variant)
    fast_response = _construct_response_model(summary_value, details_value, meta_value)

    monkeypatch.setenv(_RESPONSE_VALIDATION_ENV, "true")
    summary_validated, details_validated, meta_validated = _response_payload_variant(
        variant
    )
    validated_response = _construct_response_model(
        summary_validated, details_validated, meta_validated
    )

    assert isinstance(fast_response, CalculationResponse)
    assert isinstance(validated_response, CalculationResponse)
    assert fast_response.model_dump(mode="python", serialize_as_any=True) == (
        validated_response.model_dump(mode="python", serialize_as_any=True)
    )


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


def _employment_expectations(  # noqa: PLR0913
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
    total_employee_contrib = auto_employee_contrib + manual_requested
    if max_employee_contrib and total_employee_contrib > max_employee_contrib:
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
    reduction_base = gross_income
    if monthly_income is not None:
        payments = (
            payments_per_year
            or employment.payroll.default_payments_per_year
            or 0
        )
        if payments:
            reduction_base = monthly_income * payments
    if reduction_base > 12_000:
        credit_reduction = ((reduction_base - 12_000) / 1_000) * 20.0
    exempt_from_reduction = employment.tax_credit.income_reduction_exempt_from_dependants
    credit_after_reduction = credit_amount
    if credit_reduction > 0 and (
        exempt_from_reduction is None or children < exempt_from_reduction
    ):
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


TAXHEAVEN_EMPLOYMENT_CREDIT_EXPECTATIONS_2026 = {
    0: {
        12_000: {"tax_before": 1_300.0, "credit": 777.0},
        20_000: {"tax_before": 2_900.0, "credit": 617.0},
        30_000: {"tax_before": 5_500.0, "credit": 417.0},
        50_000: {"tax_before": 12_800.0, "credit": 17.0},
        70_000: {"tax_before": 21_100.0, "credit": 0.0},
    },
    1: {
        12_000: {"tax_before": 1_260.0, "credit": 900.0},
        20_000: {"tax_before": 2_700.0, "credit": 740.0},
        30_000: {"tax_before": 5_100.0, "credit": 540.0},
        50_000: {"tax_before": 12_400.0, "credit": 140.0},
        70_000: {"tax_before": 20_700.0, "credit": 0.0},
    },
    2: {
        12_000: {"tax_before": 1_220.0, "credit": 1_120.0},
        20_000: {"tax_before": 2_500.0, "credit": 960.0},
        30_000: {"tax_before": 4_700.0, "credit": 760.0},
        50_000: {"tax_before": 12_000.0, "credit": 360.0},
        70_000: {"tax_before": 20_300.0, "credit": 0.0},
    },
    3: {
        12_000: {"tax_before": 1_080.0, "credit": 1_080.0},
        20_000: {"tax_before": 1_800.0, "credit": 1_180.0},
        30_000: {"tax_before": 3_800.0, "credit": 980.0},
        50_000: {"tax_before": 11_100.0, "credit": 580.0},
        70_000: {"tax_before": 19_400.0, "credit": 180.0},
    },
    4: {
        12_000: {"tax_before": 0.0, "credit": 0.0},
        20_000: {"tax_before": 0.0, "credit": 0.0},
        30_000: {"tax_before": 1_800.0, "credit": 1_220.0},
        50_000: {"tax_before": 9_100.0, "credit": 820.0},
        70_000: {"tax_before": 17_400.0, "credit": 420.0},
    },
    5: {
        12_000: {"tax_before": 0.0, "credit": 0.0},
        20_000: {"tax_before": 0.0, "credit": 0.0},
        30_000: {"tax_before": 1_600.0, "credit": 1_600.0},
        50_000: {"tax_before": 8_900.0, "credit": 1_780.0},
        70_000: {"tax_before": 17_200.0, "credit": 1_780.0},
    },
    6: {
        12_000: {"tax_before": 0.0, "credit": 0.0},
        20_000: {"tax_before": 0.0, "credit": 0.0},
        30_000: {"tax_before": 1_400.0, "credit": 1_400.0},
        50_000: {"tax_before": 8_700.0, "credit": 2_000.0},
        70_000: {"tax_before": 17_000.0, "credit": 2_000.0},
    },
    7: {
        12_000: {"tax_before": 0.0, "credit": 0.0},
        20_000: {"tax_before": 0.0, "credit": 0.0},
        30_000: {"tax_before": 1_400.0, "credit": 1_400.0},
        50_000: {"tax_before": 8_700.0, "credit": 2_220.0},
        70_000: {"tax_before": 17_000.0, "credit": 2_220.0},
    },
    8: {
        12_000: {"tax_before": 0.0, "credit": 0.0},
        20_000: {"tax_before": 0.0, "credit": 0.0},
        30_000: {"tax_before": 1_400.0, "credit": 1_400.0},
        50_000: {"tax_before": 8_700.0, "credit": 2_440.0},
        70_000: {"tax_before": 17_000.0, "credit": 2_440.0},
    },
    9: {
        12_000: {"tax_before": 0.0, "credit": 0.0},
        20_000: {"tax_before": 0.0, "credit": 0.0},
        30_000: {"tax_before": 1_400.0, "credit": 1_400.0},
        50_000: {"tax_before": 8_700.0, "credit": 2_660.0},
        70_000: {"tax_before": 17_000.0, "credit": 2_660.0},
    },
    10: {
        12_000: {"tax_before": 0.0, "credit": 0.0},
        20_000: {"tax_before": 0.0, "credit": 0.0},
        30_000: {"tax_before": 1_400.0, "credit": 1_400.0},
        50_000: {"tax_before": 8_700.0, "credit": 2_880.0},
        70_000: {"tax_before": 17_000.0, "credit": 2_880.0},
    },
}


TAXHEAVEN_PUBLISHED_THRESHOLD_BEHAVIOUR_2026 = [
    (0, 8_633.0, 776.97, 776.97, 0.0),
    (1, 10_000.0, 900.0, 900.0, 0.0),
    (2, 11_375.0, 1_120.0, 1_120.0, 0.0),
    (3, 14_364.0, 1_292.76, 1_292.72, 0.04),
    (4, 27_100.0, 1_278.0, 1_278.0, 0.0),
    (5, 30_529.0, 1_779.86, 1_779.86, 0.0),
]


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


def test_2025_employment_brackets_follow_standard_schedule() -> None:
    """The 2025 employment brackets revert to the uniform 9/22/28/36/44 ladder."""

    config = load_year_configuration(2025)
    brackets = config.employment.brackets

    expected_bounds = [10_000, 20_000, 30_000, 40_000, None]
    expected_rates = [0.09, 0.22, 0.28, 0.36, 0.44]

    assert [bracket.upper_bound for bracket in brackets] == expected_bounds
    assert all(isinstance(bracket, TaxBracket) for bracket in brackets)
    assert [bracket.rate for bracket in brackets] == pytest.approx(expected_rates)


def test_2025_employment_large_family_matches_standard_brackets() -> None:
    """A 70k income with five children uses the uniform 2025 employment rates."""

    request = build_request(
        {
            "year": 2025,
            "dependents": {"children": 5},
            "employment": {"gross_income": 70_000},
            "demographics": {"taxpayer_birth_year": 1999},
        }
    )

    result = calculate_tax(request)

    summary = result["summary"]
    employment_detail = next(
        detail for detail in result["details"] if detail["category"] == "employment"
    )

    assert summary["tax_total"] == pytest.approx(16_802.04, rel=1e-4)
    assert employment_detail["taxable_income"] == pytest.approx(60_641.0)
    assert employment_detail["tax_before_credits"] == pytest.approx(18_582.04)
    assert employment_detail["credits"] == pytest.approx(1_780.0)


def test_2026_employment_brackets_match_taxheaven_tables() -> None:
    """The 2026 employment brackets mirror the Taxheaven dependant ladders."""

    config = load_year_configuration(2026)
    brackets = config.employment.brackets

    expected_bounds = [10_000, 20_000, 30_000, 40_000, 60_000, None]
    assert [bracket.upper_bound for bracket in brackets] == expected_bounds

    expected_household_rates = {
        0: [0.09, 0.20, 0.26, 0.34, 0.39, 0.44],
        1: [0.09, 0.18, 0.24, 0.34, 0.39, 0.44],
        2: [0.09, 0.16, 0.22, 0.34, 0.39, 0.44],
        3: [0.09, 0.09, 0.20, 0.34, 0.39, 0.44],
        4: [0.0, 0.0, 0.18, 0.34, 0.39, 0.44],
        5: [0.0, 0.0, 0.16, 0.34, 0.39, 0.44],
        6: [0.0, 0.0, 0.14, 0.34, 0.39, 0.44],
    }

    for dependants, expected_rates in expected_household_rates.items():
        actual_rates = [
            bracket.rate_for_dependants(dependants) for bracket in brackets
        ]
        assert actual_rates == pytest.approx(expected_rates)

    expected_under_25_rates = {
        0: [0.0, 0.0, 0.26, 0.34, 0.39, 0.44],
        1: [0.0, 0.0, 0.24, 0.34, 0.39, 0.44],
        2: [0.0, 0.0, 0.22, 0.34, 0.39, 0.44],
        3: [0.0, 0.0, 0.20, 0.34, 0.39, 0.44],
        4: [0.0, 0.0, 0.18, 0.34, 0.39, 0.44],
        5: [0.0, 0.0, 0.16, 0.34, 0.39, 0.44],
        6: [0.0, 0.0, 0.14, 0.34, 0.39, 0.44],
    }

    for dependants, expected_rates in expected_under_25_rates.items():
        actual_rates = [
            bracket.youth_rate_for_dependants("under_25", dependants)
            for bracket in brackets
        ]
        assert actual_rates == pytest.approx(expected_rates)

    expected_age26_30_rates = {
        0: [0.09, 0.09, 0.26, 0.34, 0.39, 0.44],
        1: [0.09, 0.09, 0.24, 0.34, 0.39, 0.44],
        2: [0.09, 0.09, 0.22, 0.34, 0.39, 0.44],
        3: [0.09, 0.09, 0.20, 0.34, 0.39, 0.44],
        4: [0.0, 0.0, 0.18, 0.34, 0.39, 0.44],
        5: [0.0, 0.0, 0.16, 0.34, 0.39, 0.44],
        6: [0.0, 0.0, 0.14, 0.34, 0.39, 0.44],
    }

    for dependants, expected_rates in expected_age26_30_rates.items():
        actual_rates = [
            bracket.youth_rate_for_dependants("age26_30", dependants)
            for bracket in brackets
        ]
        assert actual_rates == pytest.approx(expected_rates)


def test_2026_large_family_credit_not_reduced() -> None:
    """Five-child households retain the full 2026 family tax credit despite income."""

    request = build_request(
        {
            "year": 2026,
            "dependents": {"children": 5},
            "employment": {
                "gross_income": 70_000,
                "include_social_contributions": False,
            },
        }
    )

    result = calculate_tax(request)

    summary = result["summary"]
    employment_detail = next(
        detail for detail in result["details"] if detail["category"] == "employment"
    )

    assert employment_detail["tax_before_credits"] == pytest.approx(17_200.0)
    assert employment_detail["credits"] == pytest.approx(1_780.0)
    assert employment_detail["total_tax"] == pytest.approx(15_420.0)
    assert summary["net_income"] == pytest.approx(54_580.0)


@pytest.mark.parametrize(
    "dependants, expectations",
    list(TAXHEAVEN_EMPLOYMENT_CREDIT_EXPECTATIONS_2026.items()),
)
def test_2026_employment_credit_regression_against_taxheaven(
    dependants: int, expectations: dict[int, dict[str, float]]
) -> None:
    """Employment credit and pre-credit tax mirror the Taxheaven reference across brackets."""

    for income in sorted(expectations):
        request = build_request(
            {
                "year": 2026,
                "dependents": {"children": dependants},
                "employment": {
                    "gross_income": income,
                    "include_social_contributions": False,
                },
            }
        )

        result = calculate_tax(request)
        employment_detail = next(
            detail for detail in result["details"] if detail["category"] == "employment"
        )

        expected = expectations[income]
        assert employment_detail["tax_before_credits"] == pytest.approx(
            expected["tax_before"], abs=0.01
        )
        assert employment_detail["credits"] == pytest.approx(
            expected["credit"], abs=0.01
        )


@pytest.mark.parametrize(
    "dependants, published_income, expected_before, expected_credit, expected_tax",
    TAXHEAVEN_PUBLISHED_THRESHOLD_BEHAVIOUR_2026,
)
def test_2026_taxheaven_threshold_behaviour(
    dependants: int,
    published_income: float,
    expected_before: float,
    expected_credit: float,
    expected_tax: float,
) -> None:
    """Published “tax-free” thresholds still respect the credit reduction rule."""

    request = build_request(
        {
            "year": 2026,
            "dependents": {"children": dependants},
            "employment": {
                "gross_income": published_income,
                "include_social_contributions": False,
            },
        }
    )

    result = calculate_tax(request)
    employment_detail = next(
        detail for detail in result["details"] if detail["category"] == "employment"
    )

    assert employment_detail["tax_before_credits"] == pytest.approx(
        expected_before, abs=0.01
    )
    assert employment_detail["credits"] == pytest.approx(
        expected_credit, abs=0.01
    )
    assert employment_detail["total_tax"] == pytest.approx(expected_tax, abs=0.01)


@pytest.mark.parametrize(
    "dependants, zero_income, next_euro",
    [
        (3, 14_363.0, 14_364.0),
        (4, 27_100.0, 27_101.0),
    ],
)
def test_2026_credit_zero_tax_cutover(
    dependants: int, zero_income: float, next_euro: float
) -> None:
    """Medium households hit zero tax below the Taxheaven allowances."""

    request_zero = build_request(
        {
            "year": 2026,
            "dependents": {"children": dependants},
            "employment": {
                "gross_income": zero_income,
                "include_social_contributions": False,
            },
        }
    )
    result_zero = calculate_tax(request_zero)
    employment_zero = next(
        detail for detail in result_zero["details"] if detail["category"] == "employment"
    )
    assert employment_zero["total_tax"] == pytest.approx(0.0, abs=0.01)
    assert employment_zero["tax_before_credits"] == pytest.approx(
        employment_zero["credits"], abs=0.01
    )

    request_next = build_request(
        {
            "year": 2026,
            "dependents": {"children": dependants},
            "employment": {
                "gross_income": next_euro,
                "include_social_contributions": False,
            },
        }
    )
    result_next = calculate_tax(request_next)
    employment_next = next(
        detail for detail in result_next["details"] if detail["category"] == "employment"
    )
    assert employment_next["total_tax"] > 0.0
    assert employment_next["tax_before_credits"] > employment_next["credits"]


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
    total_employee_contrib = auto_employee_contrib + manual_requested
    if max_employee_contrib and total_employee_contrib > max_employee_contrib:
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
        calculate_tax(
            {
                "year": 2024,
                "employment": {"gross_income": -10},
                "demographics": {"birth_year": 1985},
            }
        )

    message = str(error.value)
    assert "employment.gross_income" in message
    assert "Invalid calculation payload" in message


@pytest.mark.parametrize("field", ["net_income", "net_monthly_income"])
def test_calculation_request_rejects_net_income_inputs(field: str) -> None:
    """Employment payloads should reject legacy net income fields."""

    with pytest.raises(ValidationError) as exc_info:
        build_request({"year": 2024, "employment": {field: 1_000}})

    message = str(exc_info.value)
    assert NET_INCOME_INPUT_ERROR in message


@pytest.mark.parametrize("field", ["net_income", "net_monthly_income"])
def test_calculate_tax_preserves_net_income_validation_error(field: str) -> None:
    """Service-level validation should surface the net income error message."""

    payload = {
        "year": 2024,
        "employment": {field: 1_000},
        "demographics": {"birth_year": 1985},
    }

    with pytest.raises(ValueError) as exc_info:
        calculate_tax(payload)

    message = str(exc_info.value)
    assert NET_INCOME_INPUT_ERROR in message


def test_calculation_request_allows_missing_birth_year() -> None:
    """Demographic payloads may omit the birth year entirely."""

    request = CalculationRequest.model_validate(
        {"year": 2025, "demographics": {}}
    )

    assert request.demographics.birth_year is None


def test_calculate_tax_accepts_request_model_instance() -> None:
    """The service can operate directly on a validated request model."""

    request_model = build_request(
        {"year": 2024, "employment": {"gross_income": 12_000}}
    )

    result = calculate_tax(request_model)

    expected = _employment_expectations(request_model.year, request_model.employment.gross_income)

    assert result["meta"] == {"year": 2024, "locale": "en"}
    assert result["summary"]["income_total"] == pytest.approx(12_000.0)
    assert result["summary"]["taxable_income"] == pytest.approx(expected["taxable"])


def test_calculate_tax_fast_path_skips_response_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fast-path construction should bypass Pydantic validation by default."""

    request = build_request({"year": 2024, "employment": {"gross_income": 12_000}})

    monkeypatch.delenv("GREEKTAX_VALIDATE_CALCULATION_RESPONSE", raising=False)

    def _raise_validation(cls: type, value: Any, *args: Any, **kwargs: Any) -> None:
        raise AssertionError("model_validate should not be invoked in fast path")

    monkeypatch.setattr(
        "greektax.backend.services.calculation_service.CalculationResponse.model_validate",
        classmethod(_raise_validation),
    )

    result = calculate_tax(request)

    assert result["summary"]["income_total"] == pytest.approx(12_000.0)


def test_calculate_tax_optional_validation_matches_fast_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Opt-in validation should produce the same serialised payload."""

    payload = build_request({"year": 2024, "employment": {"gross_income": 12_000}})

    monkeypatch.delenv("GREEKTAX_VALIDATE_CALCULATION_RESPONSE", raising=False)
    baseline = calculate_tax(payload)

    original_validate = CalculationResponse.model_validate
    calls: list[Any] = []

    def _counting_validate(cls: type, value: Any, *args: Any, **kwargs: Any):
        calls.append(value)
        return original_validate(value, *args, **kwargs)

    monkeypatch.setattr(
        "greektax.backend.services.calculation_service.CalculationResponse.model_validate",
        classmethod(_counting_validate),
    )
    monkeypatch.setenv("GREEKTAX_VALIDATE_CALCULATION_RESPONSE", "true")

    validated = calculate_tax(payload)

    assert calls, "Expected validation to run when debug flag is enabled"
    assert validated == baseline


def test_calculate_tax_defaults_to_zero_summary() -> None:
    """An empty payload (besides year) should produce zeroed totals."""

    request = build_request({"year": 2024})

    result = calculate_tax(request)

    assert result["summary"]["income_total"] == 0.0
    assert result["summary"]["taxable_income"] == 0.0
    assert result["summary"]["tax_total"] == 0.0
    assert result["summary"]["net_income"] == 0.0
    assert result["summary"]["net_monthly_income"] == 0.0
    assert result["summary"]["average_monthly_tax"] == 0.0
    assert result["summary"]["effective_tax_rate"] == 0.0


def test_calculate_tax_omits_youth_relief_without_birth_year() -> None:
    """The service assumes no youth relief when no birth year is provided."""

    payload = {
        "year": 2026,
        "employment": {"gross_income": 12_000},
        "demographics": {},
    }

    result = calculate_tax(payload)

    assert result["meta"] == {"year": 2026, "locale": "en"}


def test_calculate_tax_employment_only() -> None:
    """Employment income uses progressive rates and tax credit."""

    request = build_request(
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

    request = build_request(
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

    request = build_request(
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


def test_salary_credit_reduction_uses_derived_income_when_no_declared() -> None:
    """Monthly salary inputs still reduce the credit when above the threshold."""

    request = build_request(
        {
            "year": 2024,
            "dependents": {"children": 0},
            "employment": {
                "monthly_income": 2_000,
                "payments_per_year": 14,
            },
        }
    )

    result = calculate_tax(request)
    employment_detail = result["details"][0]

    config = load_year_configuration(request.year)
    base_credit = config.employment.tax_credit.amount_for_children(
        request.dependents.children
    )

    monthly_income = request.employment.monthly_income or 0.0
    payments_per_year = request.employment.payments_per_year or 0
    derived_income = monthly_income * payments_per_year
    assert derived_income > 12_000

    reduction = ((derived_income - 12_000) / 1_000) * 20.0
    expected_credit = max(base_credit - reduction, 0.0)

    assert employment_detail["credits"] == pytest.approx(expected_credit)
    assert employment_detail["credits"] >= 0.0


def test_calculate_tax_with_withholding_tax_balance_due() -> None:
    """Withholding reduces the net tax payable and surfaces in the summary."""

    request = build_request(
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
    assert summary["labels"]["balance_due"] == "Primary tax balance (+/-)"


def test_calculate_tax_with_withholding_tax_refund() -> None:
    """Withholding greater than tax due produces a refund summary."""

    request = build_request(
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
    assert summary["labels"]["balance_due"] == "Primary tax balance (+/-)"


@pytest.mark.parametrize("payments_per_year", [14, 12])
def test_calculate_tax_accepts_monthly_employment_income(
    payments_per_year: int,
) -> None:
    """Monthly salary inputs convert to annual totals and per-payment nets."""

    request = build_request(
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

    request = build_request(
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

    request = build_request(
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

    base_request = build_request(
        {
            "year": 2024,
            "employment": {
                "monthly_income": 2_000,
                "payments_per_year": payments_per_year,
                "employee_contributions": 250,
            },
        }
    )

    excluded_request = build_request(
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

    request = build_request(
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

    request = build_request(
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

    base_request = build_request(base_payload)
    base_result = calculate_tax(base_request)
    base_detail = next(
        detail for detail in base_result["details"] if detail["category"] == "freelance"
    )

    removed_amount = base_detail.get(detail_field, 0.0)
    assert removed_amount > 0

    toggled_payload = deepcopy(base_payload)
    toggled_payload["freelance"][toggle_field] = False
    toggled_request = build_request(toggled_payload)
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
        for detail in calculate_tax(build_request(base_payload))["details"]
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
            build_request(combined_payload)
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

    request = build_request(
        {"year": 2024, "locale": "el", "employment": {"gross_income": 10_000}}
    )

    result = calculate_tax(request)

    assert result["meta"]["locale"] == "el"
    assert result["details"][0]["label"] == "Εισόδημα μισθωτών"
    assert result["summary"]["labels"]["income_total"] == "Συνολικό δηλωθέν εισόδημα"


def test_youth_relief_applies_for_under_25_birth_year() -> None:
    """Employment youth relief applies reduced bracket rates automatically."""

    base_payload = {
        "year": 2026,
        "dependents": {"children": 0},
        "employment": {"gross_income": 20_000},
        "demographics": {"birth_year": 2003},
    }

    youth_request = build_request(base_payload)
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

    baseline_request = build_request(
        {**base_payload, "demographics": {"birth_year": 1985}}
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
        "demographics": {"birth_year": 1999},
    }

    youth_request = build_request(base_payload)
    youth_result = calculate_tax(youth_request)
    youth_detail = next(
        detail for detail in youth_result["details"] if detail["category"] == "employment"
    )

    assert youth_detail["taxable_income"] == pytest.approx(20_000)
    assert youth_detail["tax_before_credits"] == pytest.approx(1_800, rel=1e-4)

    baseline_request = build_request(
        {**base_payload, "demographics": {"birth_year": 1985}}
    )
    baseline_result = calculate_tax(baseline_request)
    baseline_detail = next(
        detail for detail in baseline_result["details"] if detail["category"] == "employment"
    )

    assert baseline_detail["taxable_income"] == pytest.approx(20_000)
    assert baseline_detail["tax_before_credits"] == pytest.approx(2_900, rel=1e-4)
    assert youth_detail["tax_before_credits"] < baseline_detail["tax_before_credits"]


def test_2026_youth_relief_applies_to_freelance_income() -> None:
    """Youth relief extends to freelance profit for the 2026 scale."""

    base_payload = {
        "year": 2026,
        "dependents": {"children": 0},
        "freelance": {"profit": 20_000},
        "demographics": {"birth_year": 2003},
    }

    youth_request = build_request(base_payload)
    youth_result = calculate_tax(youth_request)

    freelance_detail = next(
        detail for detail in youth_result["details"] if detail["category"] == "freelance"
    )

    assert freelance_detail["taxable_income"] == pytest.approx(20_000)
    assert freelance_detail["tax_before_credits"] == pytest.approx(0.0, rel=1e-4)

    baseline_request = build_request(
        {**base_payload, "demographics": {"birth_year": 1985}}
    )
    baseline_result = calculate_tax(baseline_request)
    baseline_detail = next(
        detail for detail in baseline_result["details"] if detail["category"] == "freelance"
    )

    expected_baseline_tax = 10_000 * 0.09 + 10_000 * 0.20

    assert baseline_detail["tax_before_credits"] == pytest.approx(
        expected_baseline_tax, rel=1e-4
    )
    assert baseline_detail["tax_before_credits"] > freelance_detail["tax_before_credits"]


def test_2026_youth_relief_applies_to_agricultural_income() -> None:
    """Agricultural income also benefits from the youth relief brackets in 2026."""

    base_payload = {
        "year": 2026,
        "dependents": {"children": 0},
        "agricultural": {"gross_revenue": 20_000},
        "demographics": {"birth_year": 1999},
    }

    youth_request = build_request(base_payload)
    youth_result = calculate_tax(youth_request)
    agricultural_detail = next(
        detail
        for detail in youth_result["details"]
        if detail["category"] == "agricultural"
    )

    assert agricultural_detail["taxable_income"] == pytest.approx(20_000)
    assert agricultural_detail["tax_before_credits"] == pytest.approx(1_800, rel=1e-4)

    baseline_request = build_request(
        {**base_payload, "demographics": {"birth_year": 1985}}
    )
    baseline_result = calculate_tax(baseline_request)
    baseline_detail = next(
        detail
        for detail in baseline_result["details"]
        if detail["category"] == "agricultural"
    )

    expected_baseline_tax = 10_000 * 0.09 + 10_000 * 0.20

    assert baseline_detail["tax_before_credits"] == pytest.approx(
        expected_baseline_tax, rel=1e-4
    )
    assert baseline_detail["tax_before_credits"] > agricultural_detail["tax_before_credits"]


def test_2026_under_25_dependant_rates_match_announced_scale() -> None:
    """Dependants adjust youth relief brackets according to the 2026 scale."""

    base_payload = {
        "year": 2026,
        "dependents": {"children": 2},
        "employment": {
            "gross_income": 30_000,
            "include_social_contributions": False,
        },
        "demographics": {"birth_year": 2004},
    }

    youth_request = build_request(base_payload)
    youth_result = calculate_tax(youth_request)
    youth_detail = next(
        detail for detail in youth_result["details"] if detail["category"] == "employment"
    )

    assert youth_detail["taxable_income"] == pytest.approx(30_000)
    assert youth_detail["tax_before_credits"] == pytest.approx(2_200, rel=1e-4)

    baseline_request = build_request(
        {**base_payload, "demographics": {"birth_year": 1985}}
    )
    baseline_result = calculate_tax(baseline_request)
    baseline_detail = next(
        detail for detail in baseline_result["details"] if detail["category"] == "employment"
    )

    assert baseline_detail["tax_before_credits"] == pytest.approx(4_700, rel=1e-4)
    assert youth_detail["tax_before_credits"] < baseline_detail["tax_before_credits"]


def test_2025_birth_year_above_limit_rejected_with_income() -> None:
    """Birth years after 2025 are rejected when income is supplied."""

    payload = {
        "year": 2025,
        "employment": {"gross_income": 5_000},
        "demographics": {"taxpayer_birth_year": 2026},
    }

    with pytest.raises(ValueError) as exc_info:
        calculate_tax(payload)

    message = str(exc_info.value)
    assert "birth_year" in message


def test_birth_year_above_limit_rejected_without_income() -> None:
    """Birth years beyond the allowed window fail validation even without income."""

    payload = {
        "year": 2025,
        "demographics": {"birth_year": 2026},
    }

    with pytest.raises(ValueError) as exc_info:
        calculate_tax(payload)

    assert "birth_year" in str(exc_info.value)


def test_dependents_children_cannot_exceed_supported_limit() -> None:
    """Household child counts above fifteen are rejected."""

    payload = {
        "year": 2025,
        "dependents": {"children": 16},
        "demographics": {"birth_year": 1990},
    }

    with pytest.raises(ValueError) as exc_info:
        calculate_tax(payload)

    assert "dependents.children" in str(exc_info.value)


def test_youth_band_classifies_age_twenty_five_in_reference_year() -> None:
    """Youth band derivation treats the reference age of 25 as under 25."""

    request = build_request(
        {
            "year": 2025,
            "employment": {"gross_income": 15_000},
            "demographics": {"taxpayer_birth_year": 2001},
        }
    )

    result = calculate_tax(request)

    assert result["meta"]["youth_relief_category"] == "under_25"


def test_calculate_tax_combines_employment_and_pension_credit() -> None:
    """Salary and pension income share a single tax credit."""

    request = build_request(
        {
            "year": 2024,
            "dependents": {"children": 1},
            "employment": {"gross_income": 10_000},
            "pension": {"gross_income": 10_000},
        }
    )

    result = calculate_tax(request)

    assert result["summary"]["tax_total"] == pytest.approx(2_054.86, rel=1e-4)
    assert result["summary"]["taxable_income"] == pytest.approx(18_613.0)
    assert result["summary"]["net_income"] == pytest.approx(16_558.14, rel=1e-4)

    employment_detail = next(
        detail for detail in result["details"] if detail["category"] == "employment"
    )
    pension_detail = next(
        detail for detail in result["details"] if detail["category"] == "pension"
    )

    assert employment_detail["tax_before_credits"] == pytest.approx(1_293.3, rel=1e-4)
    assert pension_detail["tax_before_credits"] == pytest.approx(1_501.56, rel=1e-4)

    assert employment_detail["credits"] == pytest.approx(342.43, rel=1e-4)
    assert pension_detail["credits"] == pytest.approx(397.57, rel=1e-4)

    assert employment_detail["total_tax"] == pytest.approx(950.87, rel=1e-4)
    assert pension_detail["total_tax"] == pytest.approx(1_103.99, rel=1e-4)
    assert employment_detail["employee_contributions"] == pytest.approx(1_387.0)


def test_calculate_tax_with_pension_and_rental_income() -> None:
    request = build_request(
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

    # Pension tax: (10k * 9%) + (8k * 22%) = 900 + 1,760 = 2,660
    # Credit for 2 children = 1,120 reduced by €120 above the threshold -> tax 1,660
    assert pension_detail["total_tax"] == pytest.approx(1_660.0)

    # Rental taxable: 15k - 2k = 13k -> 12k @15% + 1k @35% = 2,150
    assert rental_detail["taxable_income"] == pytest.approx(13_000.0)
    assert rental_detail["total_tax"] == pytest.approx(2_150.0)
    assert rental_detail["net_income"] == pytest.approx(10_850.0)

    assert result["summary"]["income_total"] == pytest.approx(33_000.0)
    assert result["summary"]["taxable_income"] == pytest.approx(31_000.0)
    assert result["summary"]["tax_total"] == pytest.approx(3_810.0)


def test_calculate_tax_with_investment_income_breakdown() -> None:
    request = build_request(
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
    request = build_request(
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

    request_2024 = build_request({"year": 2024, **base_payload})
    request_2025 = build_request({"year": 2025, **base_payload})
    request_2026 = build_request({"year": 2026, **base_payload})

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

    assert expected_2025["credit"] == pytest.approx(expected_2024["credit"])
    assert expected_2026["credit"] == pytest.approx(expected_2025["credit"])
    assert result_2026["meta"]["year"] == request_2026.year
def test_2026_dependant_credit_tiers_match_taxheaven_schedule() -> None:
    """Dependent credit tiers for 2026 match the Taxheaven-published ladder."""

    config = load_year_configuration(2026)
    credit = config.employment.tax_credit

    assert credit.pending_confirmation is True
    assert credit.incremental_amount_per_child == pytest.approx(220.0)
    expected_amounts = {
        0: 777.0,
        1: 900.0,
        2: 1_120.0,
        3: 1_340.0,
        4: 1_580.0,
        5: 1_780.0,
        6: 2_000.0,
        7: 2_220.0,
        8: 2_440.0,
        9: 2_660.0,
        10: 2_880.0,
        11: 3_100.0,
        12: 3_320.0,
        13: 3_540.0,
        14: 3_760.0,
        15: 3_980.0,
    }

    for dependants, amount in expected_amounts.items():
        assert credit.amount_for_children(dependants) == pytest.approx(amount)

    # The incremental amount applies beyond the published table.
    assert credit.amount_for_children(16) == pytest.approx(4_200.0)


def test_2026_rental_mid_band_cut() -> None:
    """Rental income applies the reduced mid-band threshold introduced for 2026."""

    request = build_request(
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

    request = build_request(
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

    request = build_request(
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

    request = build_request(
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

    base_request = build_request(
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

    base_request = build_request(
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

    request_2024 = build_request(
        {"year": 2024, "freelance": {"profit": 12_000}}
    )
    result_2024 = calculate_tax(request_2024)
    freelance_2024 = next(
        detail for detail in result_2024["details"] if detail["category"] == "freelance"
    )
    assert freelance_2024["trade_fee"] == pytest.approx(0.0)

    request_2025 = build_request(
        {"year": 2025, "freelance": {"profit": 12_000}}
    )
    result_2025 = calculate_tax(request_2025)
    freelance_2025 = next(
        detail for detail in result_2025["details"] if detail["category"] == "freelance"
    )
    assert freelance_2025["trade_fee"] == pytest.approx(0.0)

    assert result_2025["summary"]["tax_total"] == pytest.approx(1_340.0)
    assert result_2025["summary"]["tax_total"] <= result_2024["summary"]["tax_total"]


def test_calculate_tax_with_agricultural_and_other_income() -> None:
    """Agricultural and other income categories produce dedicated details."""

    request = build_request(
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


def test_agricultural_only_income_has_no_salary_credit_in_2025() -> None:
    """Agricultural-only income no longer benefits from the salary tax credit."""

    request = build_request(
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

    assert agricultural_detail["credits"] == pytest.approx(0.0)
    assert agricultural_detail["tax"] == pytest.approx(
        agricultural_detail["tax_before_credits"]
    )


def test_professional_farmer_credit_removed_for_2025() -> None:
    """Professional farmers no longer receive the employment tax credit in 2025."""

    request = build_request(
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

    assert agricultural_detail["credits"] == pytest.approx(0.0)

def test_calculate_tax_trade_fee_reduction_rules() -> None:
    """Trade fee toggles keep the amount at zero after the abolition."""

    config = load_year_configuration(2025)
    trade_fee_config = config.freelance.trade_fee

    base_request = build_request(
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
