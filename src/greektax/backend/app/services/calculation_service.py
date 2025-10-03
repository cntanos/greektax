"""Business logic for tax calculations."""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from numbers import Real
from time import perf_counter
from types import MappingProxyType
from typing import Any

from pydantic import ValidationError

from greektax.backend.app.localization import Translator, get_translator
from greektax.backend.app.models import (
    CalculationInput,
    CalculationRequest,
    CalculationResponse,
    DetailTotals,
    GeneralIncomeComponent,
    format_validation_error,
)
from greektax.backend.config.year_config import (
    FreelanceConfig,
    InvestmentConfig,
    PayrollConfig,
    RentalConfig,
    TaxBracket,
    YearConfiguration,
    load_year_configuration,
)

_LOGGER = logging.getLogger(__name__)


# Conservative approximations of statutory deduction rules. They can be
# refined per tax-year configuration when more granular data becomes
# available, but prevent over-application of relief in the meantime.
_DONATIONS_CREDIT_RATE = 0.20
_DONATIONS_INCOME_CAP_RATE = 0.10
_MEDICAL_CREDIT_RATE = 0.10
_MEDICAL_INCOME_THRESHOLD_RATE = 0.05
_MEDICAL_MAX_CREDIT = 3_000.0
_EDUCATION_CREDIT_RATE = 0.10
_EDUCATION_MAX_ELIGIBLE_EXPENSE = 1_000.0
_INSURANCE_CREDIT_RATE = 0.10
_INSURANCE_MAX_ELIGIBLE_EXPENSE = 1_200.0


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
    if freelance_input.profit is None:
        profit = freelance_input.gross_revenue - freelance_input.deductible_expenses
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
    vat_due = obligations.vat
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
        withholding_tax=withholding_tax,
        pension_income=pension_income,
        pension_monthly_income=pension_monthly_income,
        pension_payments_per_year=pension_payments,
        pension_net_target_income=pension_net_target,
        freelance_profit=profit,
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
        vat_due=vat_due,
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


def _calculate_progressive_tax(amount: float, brackets: Sequence[TaxBracket]) -> float:
    if amount <= 0:
        return 0.0

    total = 0.0
    lower_bound = 0.0

    for bracket in brackets:
        upper = bracket.upper_bound
        if upper is None or amount < upper:
            total += (amount - lower_bound) * bracket.rate
            break

        total += (upper - lower_bound) * bracket.rate
        lower_bound = upper

    return total


def _calculate_trade_fee(payload: CalculationInput, config: FreelanceConfig) -> float:
    if not payload.include_trade_fee:
        return 0.0
    if payload.freelance_taxable_income <= 0:
        return 0.0

    sunset = config.trade_fee.sunset
    if sunset is not None:
        status_key = (sunset.status_key or "").strip().lower()
        if status_key.endswith("scheduled"):
            scheduled_year = sunset.year
            if scheduled_year is None:
                return 0.0
            if payload.year >= scheduled_year - 1:
                return 0.0

    amount = config.trade_fee.standard_amount

    if (
        payload.freelance_trade_fee_location == "reduced"
        and config.trade_fee.reduced_amount is not None
    ):
        amount = config.trade_fee.reduced_amount

    if payload.freelance_newly_self_employed:
        years_active = payload.freelance_years_active or 0
        reduction_years = config.trade_fee.newly_self_employed_reduction_years
        if reduction_years is not None and years_active < reduction_years:
            if config.trade_fee.reduced_amount is not None:
                amount = min(amount, config.trade_fee.reduced_amount)
            else:
                amount = 0.0

    return amount if amount > 0 else 0.0


def _apply_deduction_credits(
    payload: CalculationInput,
    components: Sequence[GeneralIncomeComponent],
    translator: Translator,
) -> tuple[float, list[dict[str, Any]]]:
    credit_eligible_components = [
        component for component in components if component.credit_eligible
    ]
    available_tax = sum(
        component.tax_after_credit for component in credit_eligible_components
    )
    income_for_thresholds = sum(
        component.gross_income for component in credit_eligible_components
    )

    breakdown: list[dict[str, Any]] = []

    def _append_breakdown(
        entry_type: str,
        amounts: tuple[float, float, float],
        requested: float,
        note: str | None = None,
    ) -> None:
        entered, eligible, rate = amounts
        breakdown.append(
            {
                "type": entry_type,
                "label": translator(f"forms.deductions.{entry_type}"),
                "entered": entered,
                "eligible": eligible,
                "credit_rate": rate,
                "credit_requested": requested,
                "credit_applied": 0.0,
                "notes": note,
            }
        )

    donations = max(payload.deductions_donations, 0.0)
    if donations > 0:
        if income_for_thresholds > 0:
            income_cap = income_for_thresholds * _DONATIONS_INCOME_CAP_RATE
            eligible = min(donations, income_cap)
            note = None
            if donations > income_cap:
                note = (
                    "Only donations up to 10% of eligible income qualify for the 20% credit."
                )
        else:
            eligible = 0.0
            note = "Donations cannot generate a credit without taxable income."
        requested = eligible * _DONATIONS_CREDIT_RATE
        _append_breakdown(
            "donations",
            (donations, eligible, _DONATIONS_CREDIT_RATE),
            requested,
            note,
        )

    medical = max(payload.deductions_medical, 0.0)
    if medical > 0:
        if income_for_thresholds > 0:
            threshold = income_for_thresholds * _MEDICAL_INCOME_THRESHOLD_RATE
            eligible_expense = max(medical - threshold, 0.0)
            note = None
            if medical <= threshold:
                note = "Medical expenses must exceed 5% of income before a credit is granted."
        else:
            eligible_expense = 0.0
            note = "Medical credits require taxable income to satisfy the 5% threshold."
        requested = eligible_expense * _MEDICAL_CREDIT_RATE
        if requested > _MEDICAL_MAX_CREDIT:
            requested = _MEDICAL_MAX_CREDIT
            extra_note = (
                "Medical expense credits are capped at €3,000 per taxpayer."
            )
            note = f"{note} {extra_note}".strip() if note else extra_note
        _append_breakdown(
            "medical",
            (medical, eligible_expense, _MEDICAL_CREDIT_RATE),
            requested,
            note,
        )

    education = max(payload.deductions_education, 0.0)
    if education > 0:
        eligible = min(education, _EDUCATION_MAX_ELIGIBLE_EXPENSE)
        note = None
        if education > _EDUCATION_MAX_ELIGIBLE_EXPENSE:
            note = (
                "Education expenses eligible for credits are capped; excess is ignored."
            )
        requested = eligible * _EDUCATION_CREDIT_RATE
        _append_breakdown(
            "education",
            (education, eligible, _EDUCATION_CREDIT_RATE),
            requested,
            note,
        )

    insurance = max(payload.deductions_insurance, 0.0)
    if insurance > 0:
        eligible = min(insurance, _INSURANCE_MAX_ELIGIBLE_EXPENSE)
        note = None
        if insurance > _INSURANCE_MAX_ELIGIBLE_EXPENSE:
            note = (
                "Life and health insurance premiums have a statutory ceiling for credits."
            )
        requested = eligible * _INSURANCE_CREDIT_RATE
        _append_breakdown(
            "insurance",
            (insurance, eligible, _INSURANCE_CREDIT_RATE),
            requested,
            note,
        )

    total_requested = sum(item["credit_requested"] for item in breakdown)
    if total_requested <= 0:
        return 0.0, breakdown

    scaling_factor = 1.0
    if total_requested > available_tax:
        scaling_factor = available_tax / total_requested if total_requested > 0 else 0.0
        for item in breakdown:
            existing_note = item.get("notes")
            limitation_note = (
                "Credits were limited by the remaining tax liability."
            )
            item["notes"] = (
                f"{existing_note} {limitation_note}".strip()
                if existing_note
                else limitation_note
            )

    total_applied = 0.0
    for item in breakdown:
        applied = item["credit_requested"] * scaling_factor
        item["credit_applied"] = applied
        total_applied += applied

    if total_applied <= 0:
        return 0.0, breakdown

    if available_tax <= 0:
        return 0.0, breakdown

    for component in credit_eligible_components:
        share = (
            component.tax_after_credit / available_tax if available_tax > 0 else 0.0
        )
        credit_share = total_applied * share
        if credit_share <= 0:
            continue
        component.deductions_applied = credit_share
        component.tax_after_credit = max(component.tax_after_credit - credit_share, 0.0)

    return total_applied, breakdown


def _build_general_income_components(
    payload: CalculationInput, config: YearConfiguration
) -> list[GeneralIncomeComponent]:
    components: list[GeneralIncomeComponent] = []

    if payload.has_employment_income:
        auto_employee_contrib = (
            payload.employment_income * config.employment.contributions.employee_rate
        )
        employee_manual_contrib = payload.employment_manual_contributions
        employee_contrib = auto_employee_contrib + employee_manual_contrib
        employer_contrib = (
            payload.employment_income * config.employment.contributions.employer_rate
        )
        monthly_income = payload.employment_monthly_income
        if (
            monthly_income is None
            and payload.employment_payments_per_year
            and payload.employment_payments_per_year > 0
        ):
            monthly_income = payload.employment_income / payload.employment_payments_per_year

        components.append(
            GeneralIncomeComponent(
                category="employment",
                label_key="details.employment",
                gross_income=payload.employment_income,
                taxable_income=payload.employment_income,
                credit_eligible=True,
                payments_per_year=payload.employment_payments_per_year,
                monthly_gross_income=monthly_income,
                employee_contributions=employee_contrib,
                employee_manual_contributions=employee_manual_contrib,
                employer_contributions=employer_contrib,
            )
        )

    if payload.has_pension_income:
        employee_contrib = (
            payload.pension_income * config.pension.contributions.employee_rate
        )
        employer_contrib = (
            payload.pension_income * config.pension.contributions.employer_rate
        )
        monthly_income = payload.pension_monthly_income
        if (
            monthly_income is None
            and payload.pension_payments_per_year
            and payload.pension_payments_per_year > 0
        ):
            monthly_income = payload.pension_income / payload.pension_payments_per_year

        components.append(
            GeneralIncomeComponent(
                category="pension",
                label_key="details.pension",
                gross_income=payload.pension_income,
                taxable_income=payload.pension_income,
                credit_eligible=True,
                payments_per_year=payload.pension_payments_per_year,
                monthly_gross_income=monthly_income,
                employee_contributions=employee_contrib,
                employer_contributions=employer_contrib,
            )
        )

    if payload.has_freelance_activity:
        trade_fee = _calculate_trade_fee(payload, config.freelance)
        components.append(
            GeneralIncomeComponent(
                category="freelance",
                label_key="details.freelance",
                gross_income=payload.freelance_profit,
                taxable_income=payload.freelance_taxable_income,
                credit_eligible=True,
                contributions=payload.total_freelance_contributions,
                category_contributions=payload.freelance_category_contribution,
                additional_contributions=payload.freelance_additional_contributions,
                auxiliary_contributions=payload.freelance_auxiliary_contributions,
                lump_sum_contributions=payload.freelance_lump_sum_contributions,
                trade_fee=trade_fee,
            )
        )

    if payload.has_agricultural_income:
        components.append(
            GeneralIncomeComponent(
                category="agricultural",
                label_key="details.agricultural",
                gross_income=payload.agricultural_gross_revenue,
                taxable_income=payload.agricultural_profit,
                credit_eligible=payload.qualifies_for_agricultural_tax_credit,
                deductible_expenses=payload.agricultural_deductible_expenses,
            )
        )

    if payload.has_other_income:
        components.append(
            GeneralIncomeComponent(
                category="other",
                label_key="details.other",
                gross_income=payload.other_taxable_income,
                taxable_income=payload.other_taxable_income,
                credit_eligible=False,
            )
        )

    return components


def _apply_progressive_tax(
    components: Sequence[GeneralIncomeComponent],
    payload: CalculationInput,
    config: YearConfiguration,
) -> None:
    if not components:
        return

    total_taxable = sum(component.taxable_income for component in components)
    tax_before_credit = _calculate_progressive_tax(
        total_taxable, config.employment.brackets
    )

    credit_candidates: list[float] = []
    if any(component.category == "employment" for component in components):
        credit_candidates.append(
            config.employment.tax_credit.amount_for_children(payload.children)
        )
    if any(component.category == "pension" for component in components):
        credit_candidates.append(
            config.pension.tax_credit.amount_for_children(payload.children)
        )
    if any(
        component.category == "agricultural" and component.credit_eligible
        for component in components
    ):
        credit_candidates.append(
            config.employment.tax_credit.amount_for_children(payload.children)
        )

    credit_requested = max(credit_candidates) if credit_candidates else 0.0
    credit_applied = min(credit_requested, tax_before_credit)

    if total_taxable > 0:
        for component in components:
            share = component.taxable_income / total_taxable
            component.tax_before_credit = tax_before_credit * share
    else:
        for component in components:
            component.tax_before_credit = 0.0

    eligible_tax = sum(
        component.tax_before_credit
        for component in components
        if component.credit_eligible
    )

    for component in components:
        if component.credit_eligible and eligible_tax > 0:
            share = component.tax_before_credit / eligible_tax
            component.credit = credit_applied * share
        else:
            component.credit = 0.0
        component.tax_after_credit = max(
            component.tax_before_credit - component.credit, 0.0
        )


def _rounded_component_values(
    component: GeneralIncomeComponent,
) -> tuple[float, float, float, float, float]:
    gross_income = _round_currency(component.gross_income)
    taxable_income = _round_currency(component.taxable_income)
    tax_amount = _round_currency(component.tax_after_credit)
    total_tax = _round_currency(component.total_tax())
    net_income = _round_currency(component.net_income())
    return gross_income, taxable_income, tax_amount, total_tax, net_income


def _add_deductible_expenses(detail: dict[str, Any], component: GeneralIncomeComponent) -> None:
    if component.deductible_expenses:
        detail["deductible_expenses"] = _round_currency(component.deductible_expenses)


def _add_credit_fields(detail: dict[str, Any], component: GeneralIncomeComponent) -> None:
    if component.credit_eligible:
        detail["tax_before_credits"] = _round_currency(component.tax_before_credit)
        detail["credits"] = _round_currency(component.credit)


def _add_employment_contribution_fields(
    detail: dict[str, Any], component: GeneralIncomeComponent
) -> None:
    if component.category not in {"employment", "pension"}:
        return

    if component.employee_contributions:
        detail["employee_contributions"] = _round_currency(
            component.employee_contributions
        )
        if component.employee_manual_contributions:
            detail["employee_contributions_manual"] = _round_currency(
                component.employee_manual_contributions
            )
        if component.payments_per_year:
            detail["employee_contributions_per_payment"] = _round_currency(
                component.employee_contributions / component.payments_per_year
            )

    if component.employer_contributions:
        detail["employer_contributions"] = _round_currency(
            component.employer_contributions
        )
        if component.payments_per_year:
            detail["employer_contributions_per_payment"] = _round_currency(
                component.employer_contributions / component.payments_per_year
            )


def _add_freelance_fields(
    detail: dict[str, Any], component: GeneralIncomeComponent, translator: Translator
) -> None:
    if component.category != "freelance":
        return

    detail["deductible_contributions"] = _round_currency(component.contributions)
    detail["trade_fee"] = _round_currency(component.trade_fee)
    if component.trade_fee:
        detail["trade_fee_label"] = translator("details.trade_fee")

    optional_contributions = {
        "category_contributions": component.category_contributions,
        "additional_contributions": component.additional_contributions,
        "auxiliary_contributions": component.auxiliary_contributions,
        "lump_sum_contributions": component.lump_sum_contributions,
    }

    for field, value in optional_contributions.items():
        if value:
            detail[field] = _round_currency(value)


def _add_payment_structure_fields(
    detail: dict[str, Any], component: GeneralIncomeComponent
) -> None:
    if component.monthly_gross_income is not None:
        detail["monthly_gross_income"] = _round_currency(component.monthly_gross_income)

    if not component.payments_per_year:
        return

    detail["payments_per_year"] = component.payments_per_year

    gross_per_payment = component.gross_income_per_payment()
    if gross_per_payment is not None:
        detail["gross_income_per_payment"] = _round_currency(gross_per_payment)

    net_per_payment = component.net_income_per_payment()
    if net_per_payment is not None:
        detail["net_income_per_payment"] = _round_currency(net_per_payment)


def _add_deductions_field(detail: dict[str, Any], component: GeneralIncomeComponent) -> None:
    if component.deductions_applied:
        detail["deductions_applied"] = _round_currency(component.deductions_applied)


def _detail_from_component(
    component: GeneralIncomeComponent, translator: Translator
) -> tuple[dict[str, Any], float, float, float]:
    (
        gross_income,
        taxable_income,
        tax_amount,
        total_tax,
        net_income,
    ) = _rounded_component_values(component)

    detail: dict[str, Any] = {
        "category": component.category,
        "label": translator(component.label_key),
        "gross_income": gross_income,
        "taxable_income": taxable_income,
        "tax": tax_amount,
        "total_tax": total_tax,
        "net_income": net_income,
    }

    _add_deductible_expenses(detail, component)
    _add_credit_fields(detail, component)
    _add_employment_contribution_fields(detail, component)
    _add_freelance_fields(detail, component, translator)
    _add_payment_structure_fields(detail, component)
    _add_deductions_field(detail, component)

    return detail, gross_income, total_tax, net_income


def _calculate_general_income_details(
    payload: CalculationInput,
    config: YearConfiguration,
    translator: Translator,
) -> tuple[list[dict[str, Any]], float, DetailTotals, list[dict[str, Any]]]:
    components = _build_general_income_components(payload, config)
    if not components:
        return [], 0.0, DetailTotals(), []

    _apply_progressive_tax(components, payload, config)
    deductions_applied, deduction_breakdown = _apply_deduction_credits(
        payload, components, translator
    )

    details: list[dict[str, Any]] = []
    totals = DetailTotals()
    for component in components:
        detail, gross_income, total_tax, net_income = _detail_from_component(
            component, translator
        )
        details.append(detail)
        totals.add(gross_income, total_tax, net_income)

    return details, deductions_applied, totals, deduction_breakdown


def _calculate_rental(
    payload: CalculationInput,
    config: RentalConfig,
    translator: Translator,
) -> dict[str, Any] | None:
    if not payload.has_rental_income:
        return None

    gross = payload.rental_gross_income
    expenses = payload.rental_deductible_expenses
    taxable = payload.rental_taxable_income
    tax = _calculate_progressive_tax(taxable, config.brackets)
    net_income = gross - expenses - tax

    return {
        "category": "rental",
        "label": translator("details.rental"),
        "gross_income": _round_currency(gross),
        "deductible_expenses": _round_currency(expenses),
        "taxable_income": _round_currency(taxable),
        "tax": _round_currency(tax),
        "total_tax": _round_currency(tax),
        "net_income": _round_currency(net_income),
    }


def _calculate_investment(
    payload: CalculationInput,
    config: InvestmentConfig,
    translator: Translator,
) -> dict[str, Any] | None:
    if not payload.has_investment_income:
        return None

    breakdown: list[dict[str, Any]] = []
    gross_total = 0.0
    tax_total = 0.0

    for category, rate in config.rates.items():
        amount = float(payload.investment_amounts.get(category, 0.0))
        if amount <= 0:
            continue

        tax = amount * rate
        gross_total += amount
        tax_total += tax
        breakdown.append(
            {
                "type": category,
                "label": translator(f"details.investment.{category}"),
                "amount": _round_currency(amount),
                "rate": rate,
                "tax": _round_currency(tax),
            }
        )

    if gross_total <= 0:
        return None

    net_income = gross_total - tax_total

    return {
        "category": "investment",
        "label": translator("details.investment"),
        "gross_income": _round_currency(gross_total),
        "tax": _round_currency(tax_total),
        "total_tax": _round_currency(tax_total),
        "net_income": _round_currency(net_income),
        "items": breakdown,
    }


def _round_currency(value: float) -> float:
    return round(value, 2)


def _round_rate(value: float) -> float:
    return round(value, 4)


def _calculate_vat(payload: CalculationInput, translator: Translator) -> dict[str, Any] | None:
    if not payload.has_vat_obligation:
        return None

    amount = payload.vat_due
    rounded = _round_currency(amount)
    return {
        "category": "vat",
        "label": translator("details.vat"),
        "tax": rounded,
        "total_tax": rounded,
        "net_income": _round_currency(-amount),
    }


def _calculate_enfia(payload: CalculationInput, translator: Translator) -> dict[str, Any] | None:
    if not payload.has_enfia_obligation:
        return None

    amount = payload.enfia_due
    rounded = _round_currency(amount)
    return {
        "category": "enfia",
        "label": translator("details.enfia"),
        "tax": rounded,
        "total_tax": rounded,
        "net_income": _round_currency(-amount),
    }


def _calculate_luxury(payload: CalculationInput, translator: Translator) -> dict[str, Any] | None:
    if not payload.has_luxury_obligation:
        return None

    amount = payload.luxury_due
    rounded = _round_currency(amount)
    return {
        "category": "luxury",
        "label": translator("details.luxury"),
        "tax": rounded,
        "total_tax": rounded,
        "net_income": _round_currency(-amount),
    }


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
        ) = _calculate_general_income_details(normalised, config, translator)
    details.extend(general_income_details)
    totals.merge(general_totals)

    with _profile_section("rental", timings):
        rental_detail = _calculate_rental(normalised, config.rental, translator)
    if rental_detail:
        _append_detail(rental_detail)

    with _profile_section("investment", timings):
        investment_detail = _calculate_investment(
            normalised, config.investment, translator
        )
    if investment_detail:
        _append_detail(investment_detail)

    with _profile_section("vat", timings):
        vat_detail = _calculate_vat(normalised, translator)
    if vat_detail:
        _append_detail(vat_detail)

    with _profile_section("enfia", timings):
        enfia_detail = _calculate_enfia(normalised, translator)
    if enfia_detail:
        _append_detail(enfia_detail)

    with _profile_section("luxury", timings):
        luxury_detail = _calculate_luxury(normalised, translator)
    if luxury_detail:
        _append_detail(luxury_detail)

    income_total = totals.income
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
        "income_total": _round_currency(income_total),
        "tax_total": _round_currency(tax_total),
        "net_income": _round_currency(net_income),
        "net_monthly_income": _round_currency(net_monthly_income),
        "average_monthly_tax": _round_currency(average_monthly_tax),
        "effective_tax_rate": _round_rate(effective_tax_rate),
        "deductions_entered": _round_currency(deductions_entered),
        "deductions_applied": _round_currency(deductions_applied),
        "labels": {
            "income_total": translator("summary.income_total"),
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
        summary["withholding_tax"] = _round_currency(withholding_tax)
        summary["labels"]["withholding_tax"] = translator("summary.withholding_tax")

        balance_due = tax_total - withholding_tax
        is_refund = balance_due < 0
        display_amount = -balance_due if is_refund else balance_due
        summary["balance_due"] = _round_currency(display_amount)
        summary["balance_due_is_refund"] = is_refund
        balance_label_key = "summary.refund_due" if is_refund else "summary.balance_due"
        summary["labels"]["balance_due"] = translator(balance_label_key)

    if deduction_breakdown:
        summary["deductions_breakdown"] = [
            {
                "type": entry["type"],
                "label": entry["label"],
                "entered": _round_currency(entry["entered"]),
                "eligible": _round_currency(entry["eligible"]),
                "credit_rate": entry["credit_rate"],
                "credit_requested": _round_currency(entry["credit_requested"]),
                "credit_applied": _round_currency(entry["credit_applied"]),
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
