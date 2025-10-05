"""Orchestrate request validation, normalisation, and tax calculations.

The calculation service coordinates the shared request models, translation
layer, and year-based configuration so that each income module can focus on its
own arithmetic. Profiling hooks and defensive validation live here to give the
rest of the application a simple ``calculate_tax`` entry point.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from contextlib import contextmanager
from numbers import Real
from time import perf_counter
from types import MappingProxyType
from typing import Any

from pydantic import ValidationError

from greektax.backend.app.localization import get_translator
from greektax.backend.app.models import (
    CalculationInput,
    CalculationRequest,
    CalculationResponse,
    DetailTotals,
    format_validation_error,
)
from greektax.backend.config.year_config import (
    PayrollConfig,
    YearConfiguration,
    load_year_configuration,
)

from .calculators import (
    calculate_enfia,
    calculate_general_income_details,
    calculate_investment,
    calculate_luxury,
    calculate_rental,
    round_currency,
    round_rate,
)

_LOGGER = logging.getLogger(__name__)


def _profiling_enabled() -> bool:
    """Return ``True`` when calculation profiling should be captured."""

    flag = os.getenv("GREEKTAX_PROFILE_CALCULATIONS", "")
    return flag.strip().lower() in {"1", "true", "yes", "on"}


@contextmanager
def _profile_section(name: str, store: dict[str, float] | None):
    """Capture the duration of a named section when profiling is enabled."""

    if store is None:
        yield
        return

    start = perf_counter()
    try:
        yield
    finally:
        store[name] = perf_counter() - start




def _validate_payments(
    value: int | None, payroll: PayrollConfig, field_name: str
) -> int | None:
    if value is None:
        return None

    if value < 0:
        raise ValueError(f"Field '{field_name}' cannot be negative")

    if value not in payroll.allowed_payments_per_year:
        allowed = ", ".join(str(entry) for entry in payroll.allowed_payments_per_year)
        raise ValueError(
            f"Field '{field_name}' must match an allowed payroll frequency ({allowed})"
        )
    return value




def _normalise_payload(
    request: CalculationRequest, config: YearConfiguration
) -> CalculationInput:
    locale = request.locale or "en"

    children = request.dependents.children

    employment_input = request.employment
    employment_payroll = config.employment.payroll
    employment_payments = _validate_payments(
        employment_input.payments_per_year,
        employment_payroll,
        "employment.payments_per_year",
    )

    employment_monthly_income: float | None = None
    employment_income = 0.0

    if employment_input.monthly_income is not None and employment_input.monthly_income > 0:
        payments = employment_payments or employment_payroll.default_payments_per_year
        employment_payments = payments
        employment_monthly_income = employment_input.monthly_income
        employment_income = employment_monthly_income * payments

    if employment_input.gross_income > 0:
        employment_income = employment_input.gross_income
        if employment_payments and employment_monthly_income is None:
            employment_monthly_income = employment_income / employment_payments

    employment_manual_contributions = employment_input.employee_contributions

    withholding_tax = request.withholding_tax

    freelance_input = request.freelance
    freelance_gross_revenue = freelance_input.gross_revenue
    freelance_deductible_expenses = freelance_input.deductible_expenses
    if freelance_input.profit is None:
        profit = freelance_gross_revenue - freelance_deductible_expenses
        if profit < 0:
            profit = 0.0
    else:
        profit = freelance_input.profit

    category_id = (freelance_input.efka_category or "").strip()
    category_config = None
    if category_id:
        category_config = next(
            (
                entry
                for entry in config.freelance.efka_categories
                if entry.id == category_id
            ),
            None,
        )
        if category_config is None:
            raise ValueError("Unknown EFKA category selection")

    category_months = freelance_input.efka_months
    if category_months is not None and category_months <= 0:
        category_months = None
    if category_months is None and category_config is not None:
        category_months = 12

    category_contribution = 0.0
    if category_config is not None and category_months:
        category_contribution = category_config.monthly_amount * category_months

    additional_contributions = freelance_input.mandatory_contributions
    auxiliary_contributions = freelance_input.auxiliary_contributions
    lump_sum_contributions = freelance_input.lump_sum_contributions

    include_trade_fee = freelance_input.include_trade_fee
    trade_fee_location = freelance_input.trade_fee_location
    years_active = freelance_input.years_active
    newly_self_employed = freelance_input.newly_self_employed

    pension_input = request.pension
    pension_payroll = config.pension.payroll
    pension_payments = _validate_payments(
        pension_input.payments_per_year,
        pension_payroll,
        "pension.payments_per_year",
    )

    pension_monthly_income: float | None = None
    pension_income = 0.0
    pension_net_target: float | None = None

    if pension_input.monthly_income is not None and pension_input.monthly_income > 0:
        payments = pension_payments or pension_payroll.default_payments_per_year
        pension_payments = payments
        pension_monthly_income = pension_input.monthly_income
        pension_income = pension_monthly_income * payments

    if pension_input.gross_income > 0:
        pension_income = pension_input.gross_income
        if pension_payments and pension_monthly_income is None:
            pension_monthly_income = pension_income / pension_payments

    if pension_input.net_income is not None and pension_input.net_income > 0:
        pension_net_target = pension_input.net_income

    if pension_input.net_monthly_income is not None and pension_input.net_monthly_income > 0:
        payments = pension_payments or pension_payroll.default_payments_per_year
        pension_payments = payments
        pension_net_target = pension_input.net_monthly_income * payments

    if pension_net_target is not None:
        if pension_income > 0 or (
            pension_monthly_income is not None and pension_monthly_income > 0
        ):
            raise ValueError("Provide either gross or net pension income, not both")
        if pension_payments is None:
            pension_payments = pension_payroll.default_payments_per_year
        pension_monthly_income = None
        pension_income = 0.0

    rental_input = request.rental
    rental_gross = rental_input.gross_income
    rental_expenses = rental_input.deductible_expenses

    investment_amounts = MappingProxyType(dict(request.investment))

    agricultural_input = request.agricultural
    agricultural_revenue = agricultural_input.gross_revenue
    agricultural_expenses = agricultural_input.deductible_expenses
    agricultural_professional = agricultural_input.professional_farmer

    other_income = request.other.taxable_income

    obligations = request.obligations
    enfia_due = obligations.enfia
    luxury_due = obligations.luxury

    deductions = request.deductions
    deductions_donations = deductions.donations
    deductions_medical = deductions.medical
    deductions_education = deductions.education
    deductions_insurance = deductions.insurance

    normalised = CalculationInput(
        year=request.year,
        locale=locale,
        children=children,
        employment_income=employment_income,
        employment_monthly_income=employment_monthly_income,
        employment_payments_per_year=employment_payments,
        employment_manual_contributions=employment_manual_contributions,
        employment_include_social_contributions=
        request.employment.include_social_contributions,
        withholding_tax=withholding_tax,
        pension_income=pension_income,
        pension_monthly_income=pension_monthly_income,
        pension_payments_per_year=pension_payments,
        pension_net_target_income=pension_net_target,
        freelance_profit=profit,
        freelance_gross_revenue=freelance_gross_revenue,
        freelance_deductible_expenses=freelance_deductible_expenses,
        freelance_category_id=category_config.id if category_config else None,
        freelance_category_months=category_months,
        freelance_category_contribution=category_contribution,
        freelance_additional_contributions=additional_contributions,
        freelance_auxiliary_contributions=auxiliary_contributions,
        freelance_lump_sum_contributions=lump_sum_contributions,
        include_trade_fee=include_trade_fee,
        freelance_trade_fee_location=trade_fee_location,
        freelance_years_active=years_active,
        freelance_newly_self_employed=newly_self_employed,
        rental_gross_income=rental_gross,
        rental_deductible_expenses=rental_expenses,
        investment_amounts=investment_amounts,
        enfia_due=enfia_due,
        luxury_due=luxury_due,
        agricultural_gross_revenue=agricultural_revenue,
        agricultural_deductible_expenses=agricultural_expenses,
        agricultural_professional_farmer=agricultural_professional,
        other_taxable_income=other_income,
        deductions_donations=deductions_donations,
        deductions_medical=deductions_medical,
        deductions_education=deductions_education,
        deductions_insurance=deductions_insurance,
    )

    return _apply_net_targets(normalised, config)


def _apply_net_targets(
    payload: CalculationInput, config: YearConfiguration
) -> CalculationInput:
    adjusted = payload

    if adjusted.pension_net_target_income:
        adjusted = _solve_net_target(
            adjusted,
            config,
            category="pension",
            target=adjusted.pension_net_target_income,
        )

    return adjusted


def _set_component_income(
    payload: CalculationInput, category: str, gross_income: float, payments: int
) -> CalculationInput:
    monthly_income = gross_income / payments if payments > 0 else None
    if category == "employment":
        return payload.model_copy(
            update={
                "employment_income": gross_income,
                "employment_monthly_income": monthly_income,
                "employment_payments_per_year": payments,
            }
        )

    if category == "pension":
        return payload.model_copy(
            update={
                "pension_income": gross_income,
                "pension_monthly_income": monthly_income,
                "pension_payments_per_year": payments,
            }
        )

    raise ValueError(f"Unsupported category for net target resolution: {category}")


def _solve_net_target(
    payload: CalculationInput,
    config: YearConfiguration,
    *,
    category: str,
    target: float,
) -> CalculationInput:
    if category == "employment":
        raise ValueError("Employment net income inputs are not supported")

    if target <= 0:
        return payload.model_copy(
            update={
                "pension_income": 0.0,
                "pension_monthly_income": None,
                "pension_net_target_income": None,
            }
        )

    payments = (
        payload.pension_payments_per_year
        or config.pension.payroll.default_payments_per_year
    )
    contribution_rate = config.pension.contributions.employee_rate

    highest_rate = max(bracket.rate for bracket in config.employment.brackets)

    denominator = 1.0 - contribution_rate - highest_rate
    if denominator <= 0:
        upper = target * 5 if target > 0 else 1.0
    else:
        upper = target / denominator
    upper = max(upper, target + 1.0)

    lower = max(target, 0.01)
    best_payload = payload
    best_difference = float("inf")

    for _ in range(50):
        mid = (lower + upper) / 2
        candidate = _set_component_income(payload, category, mid, payments)
        components = _build_general_income_components(candidate, config)
        _apply_progressive_tax(components, candidate, config)

        component = next(
            (entry for entry in components if entry.category == category), None
        )
        if component is None:
            break

        net_income = component.net_income()
        difference = abs(net_income - target)
        if difference < best_difference:
            best_difference = difference
            best_payload = candidate

        if difference <= 0.01:
            break

        if net_income > target:
            upper = mid
        else:
            lower = mid

    return best_payload.model_copy(update={"pension_net_target_income": None})


def _update_totals_from_detail(
    detail: Mapping[str, Any], totals: DetailTotals
) -> None:
    gross = detail.get("gross_income")
    if isinstance(gross, Real):
        totals.income += float(gross)

    tax = detail.get("total_tax")
    if isinstance(tax, Real):
        totals.tax += float(tax)

    net = detail.get("net_income")
    if isinstance(net, Real):
        totals.net += float(net)

    taxable_income = detail.get("taxable_income")
    if isinstance(taxable_income, Real):
        totals.taxable += float(taxable_income)


def calculate_tax(
    payload: Mapping[str, Any] | CalculationRequest,
) -> dict[str, Any]:
    """Compute tax summary for the provided payload."""

    if isinstance(payload, CalculationRequest):
        try:
            request_model = CalculationRequest.model_validate(
                payload.model_dump(mode="python", serialize_as_any=True)
            )
        except ValidationError as exc:
            raise ValueError(format_validation_error(exc)) from exc
    else:
        if not isinstance(payload, Mapping):
            raise ValueError("Payload must be a mapping")
        if "year" not in payload:
            raise ValueError("Payload must include a tax year")
        try:
            request_model = CalculationRequest.model_validate(payload)
        except ValidationError as exc:
            raise ValueError(format_validation_error(exc)) from exc

    timings: dict[str, float] | None = {} if _profiling_enabled() else None
    overall_start = perf_counter() if timings is not None else None

    year = request_model.year
    config: YearConfiguration = load_year_configuration(year)

    with _profile_section("normalise_payload", timings):
        normalised = _normalise_payload(request_model, config)

    translator = get_translator(normalised.locale)

    details: list[dict[str, Any]] = []
    totals = DetailTotals()

    def _append_detail(entry: Mapping[str, Any]) -> None:
        if isinstance(entry, dict):
            detail = entry
        else:
            detail = dict(entry)
        details.append(detail)
        _update_totals_from_detail(detail, totals)

    with _profile_section("general_income", timings):
        (
            general_income_details,
            deductions_applied,
            general_totals,
            deduction_breakdown,
        ) = calculate_general_income_details(normalised, config, translator)
    details.extend(general_income_details)
    totals.merge(general_totals)

    with _profile_section("rental", timings):
        rental_detail = calculate_rental(normalised, config.rental, translator)
    if rental_detail:
        _append_detail(rental_detail)

    with _profile_section("investment", timings):
        investment_detail = calculate_investment(
            normalised, config.investment, translator
        )
    if investment_detail:
        _append_detail(investment_detail)

    with _profile_section("enfia", timings):
        enfia_detail = calculate_enfia(normalised, translator)
    if enfia_detail:
        _append_detail(enfia_detail)

    with _profile_section("luxury", timings):
        luxury_detail = calculate_luxury(normalised, translator)
    if luxury_detail:
        _append_detail(luxury_detail)

    income_total = totals.income
    taxable_total = totals.taxable
    tax_total = totals.tax
    net_income = totals.net
    net_monthly_income = net_income / 12 if net_income else 0.0
    average_monthly_tax = tax_total / 12 if tax_total else 0.0
    effective_tax_rate = (tax_total / income_total) if income_total > 0 else 0.0

    deductions_entered = normalised.total_deductions

    if timings is not None and overall_start is not None:
        timings["total"] = perf_counter() - overall_start
        _LOGGER.debug(
            "calculate_tax timings (ms): %s",
            {name: round(duration * 1000, 3) for name, duration in timings.items()},
        )

    withholding_tax = normalised.withholding_tax if normalised.withholding_tax > 0 else 0.0

    summary: dict[str, Any] = {
        "income_total": round_currency(income_total),
        "taxable_income": round_currency(taxable_total),
        "tax_total": round_currency(tax_total),
        "net_income": round_currency(net_income),
        "net_monthly_income": round_currency(net_monthly_income),
        "average_monthly_tax": round_currency(average_monthly_tax),
        "effective_tax_rate": round_rate(effective_tax_rate),
        "deductions_entered": round_currency(deductions_entered),
        "deductions_applied": round_currency(deductions_applied),
        "labels": {
            "income_total": translator("summary.income_total"),
            "taxable_income": translator("summary.taxable_income"),
            "tax_total": translator("summary.tax_total"),
            "net_income": translator("summary.net_income"),
            "net_monthly_income": translator("summary.net_monthly_income"),
            "average_monthly_tax": translator("summary.average_monthly_tax"),
            "effective_tax_rate": translator("summary.effective_tax_rate"),
            "deductions_entered": translator("summary.deductions_entered"),
            "deductions_applied": translator("summary.deductions_applied"),
        },
    }

    if withholding_tax > 0:
        summary["withholding_tax"] = round_currency(withholding_tax)
        summary["labels"]["withholding_tax"] = translator("summary.withholding_tax")

        balance_due = tax_total - withholding_tax
        is_refund = balance_due < 0
        display_amount = -balance_due if is_refund else balance_due
        summary["balance_due"] = round_currency(display_amount)
        summary["balance_due_is_refund"] = is_refund
        balance_label_key = "summary.refund_due" if is_refund else "summary.balance_due"
        summary["labels"]["balance_due"] = translator(balance_label_key)

    if deduction_breakdown:
        summary["deductions_breakdown"] = [
            {
                "type": entry["type"],
                "label": entry["label"],
                "entered": round_currency(entry["entered"]),
                "eligible": round_currency(entry["eligible"]),
                "credit_rate": entry["credit_rate"],
                "credit_requested": round_currency(entry["credit_requested"]),
                "credit_applied": round_currency(entry["credit_applied"]),
                "notes": entry.get("notes"),
            }
            for entry in deduction_breakdown
        ]

    response_model = CalculationResponse.model_validate(
        {
            "summary": summary,
            "details": details,
            "meta": {
                "year": normalised.year,
                "locale": translator.locale,
            },
        }
    )

    return response_model.model_dump(mode="json")
