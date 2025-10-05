"""General income calculation helpers."""

from __future__ import annotations

from typing import Any, Sequence

from greektax.backend.app.localization import Translator
from greektax.backend.app.models import (
    CalculationInput,
    DetailTotals,
    GeneralIncomeComponent,
)
from greektax.backend.config.year_config import (
    DeductionRuleConfig,
    FreelanceConfig,
    YearConfiguration,
)

from .utils import calculate_progressive_tax, format_percentage, round_currency


def calculate_general_income_details(
    payload: CalculationInput,
    config: YearConfiguration,
    translator: Translator,
) -> tuple[list[dict[str, Any]], float, DetailTotals, list[dict[str, Any]]]:
    """Build detailed general income breakdown and deduction data."""

    components = _build_general_income_components(payload, config)
    if not components:
        return [], 0.0, DetailTotals(), []

    _apply_progressive_tax(components, payload, config)
    deductions_applied, deduction_breakdown = _apply_deduction_credits(
        payload, components, translator, config.deductions.rules
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


def _build_general_income_components(
    payload: CalculationInput, config: YearConfiguration
) -> list[GeneralIncomeComponent]:
    components: list[GeneralIncomeComponent] = []

    if payload.has_employment_income:
        payments_per_year = payload.employment_payments_per_year
        if not payments_per_year or payments_per_year <= 0:
            payments_per_year = config.employment.payroll.default_payments_per_year

        monthly_income = payload.employment_monthly_income
        if monthly_income is None and payments_per_year:
            monthly_income = payload.employment_income / payments_per_year

        salary_cap = config.employment.contributions.monthly_salary_cap
        contribution_base_income = payload.employment_income
        if (
            salary_cap is not None
            and salary_cap > 0
            and payments_per_year
            and monthly_income is not None
        ):
            # Clamp the annual contribution base to the statutory EFKA ceiling so
            # auto-calculated contributions never exceed the legal maximum.
            capped_annual_income = salary_cap * payments_per_year
            contribution_base_income = min(payload.employment_income, capped_annual_income)

        include_social = payload.employment_include_social_contributions
        if include_social:
            auto_employee_contrib = (
                contribution_base_income * config.employment.contributions.employee_rate
            )
            employer_contrib = (
                contribution_base_income * config.employment.contributions.employer_rate
            )
            employee_manual_contrib = payload.employment_manual_contributions
        else:
            # When social insurance is excluded, suppress both the automatic and
            # manual EFKA amounts so the downstream net calculations become
            # purely tax-based.
            auto_employee_contrib = 0.0
            employer_contrib = 0.0
            employee_manual_contrib = 0.0

        employee_contrib = auto_employee_contrib + employee_manual_contrib
        components.append(
            GeneralIncomeComponent(
                category="employment",
                label_key="details.employment",
                gross_income=payload.employment_income,
                taxable_income=payload.employment_income,
                credit_eligible=True,
                deductible_expenses=0.0,
                employee_contributions=employee_contrib,
                employee_manual_contributions=employee_manual_contrib,
                employer_contributions=employer_contrib,
                include_employee_contributions=include_social,
                payments_per_year=payload.employment_payments_per_year,
                monthly_gross_income=payload.employment_monthly_income,
            )
        )

    if payload.has_pension_income:
        components.append(
            GeneralIncomeComponent(
                category="pension",
                label_key="details.pension",
                gross_income=payload.pension_income,
                taxable_income=payload.pension_income,
                credit_eligible=True,
                payments_per_year=payload.pension_payments_per_year,
                monthly_gross_income=payload.pension_monthly_income,
            )
        )

    if payload.has_freelance_income:
        trade_fee = _calculate_trade_fee(payload, config.freelance)
        components.append(
            GeneralIncomeComponent(
                category="freelance",
                label_key="details.freelance",
                gross_income=payload.freelance_profit,
                taxable_income=payload.freelance_taxable_income,
                credit_eligible=True,
                deductible_expenses=payload.freelance_deductible_expenses,
                contributions=payload.freelance_total_contributions,
                trade_fee=trade_fee,
                category_contributions=payload.freelance_category_contribution,
                additional_contributions=payload.freelance_additional_contributions,
                auxiliary_contributions=payload.freelance_auxiliary_contributions,
                lump_sum_contributions=payload.freelance_lump_sum_contributions,
            )
        )

    if payload.has_agricultural_income:
        components.append(
            GeneralIncomeComponent(
                category="agricultural",
                label_key="details.agricultural",
                gross_income=payload.agricultural_gross_revenue,
                taxable_income=payload.agricultural_taxable_income,
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
    tax_before_credit = calculate_progressive_tax(
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


def _apply_deduction_credits(
    payload: CalculationInput,
    components: Sequence[GeneralIncomeComponent],
    translator: Translator,
    rules: DeductionRuleConfig,
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

    donations_config = rules.donations
    donations = max(payload.deductions_donations, 0.0)
    if donations > 0:
        if income_for_thresholds > 0:
            cap_rate = donations_config.income_cap_rate
            income_cap = income_for_thresholds * cap_rate if cap_rate is not None else None
            eligible = min(donations, income_cap) if income_cap is not None else donations
            note = None
            if income_cap is not None and donations > income_cap:
                rate_label = format_percentage(donations_config.credit_rate)
                cap_label = format_percentage(cap_rate)
                note = (
                    "Only donations up to "
                    f"{cap_label} of eligible income qualify for the {rate_label} credit."
                )
        else:
            eligible = 0.0
            note = "Donations cannot generate a credit without taxable income."
        requested = eligible * donations_config.credit_rate
        _append_breakdown(
            "donations",
            (donations, eligible, donations_config.credit_rate),
            requested,
            note,
        )

    medical_config = rules.medical
    medical = max(payload.deductions_medical, 0.0)
    if medical > 0:
        if income_for_thresholds > 0:
            threshold = income_for_thresholds * medical_config.income_threshold_rate
            eligible_expense = max(medical - threshold, 0.0)
            note = None
            if medical <= threshold:
                threshold_label = format_percentage(
                    medical_config.income_threshold_rate
                )
                note = (
                    "Medical expenses must exceed "
                    f"{threshold_label} of income before a credit is granted."
                )
        else:
            eligible_expense = 0.0
            threshold_label = format_percentage(medical_config.income_threshold_rate)
            note = (
                "Medical credits require taxable income to satisfy the "
                f"{threshold_label} threshold."
            )
        requested = eligible_expense * medical_config.credit_rate
        if requested > medical_config.max_credit:
            requested = medical_config.max_credit
            extra_note = (
                "Medical expense credits are capped at "
                f"€{medical_config.max_credit:,.2f} per taxpayer."
            )
            note = f"{note} {extra_note}".strip() if note else extra_note
        _append_breakdown(
            "medical",
            (medical, eligible_expense, medical_config.credit_rate),
            requested,
            note,
        )

    education_config = rules.education
    education = max(payload.deductions_education, 0.0)
    if education > 0:
        eligible = min(education, education_config.max_eligible_expense)
        note = None
        if education > education_config.max_eligible_expense:
            note = (
                "Education expenses eligible for credits are capped at "
                f"€{education_config.max_eligible_expense:,.2f}; excess is ignored."
            )
        requested = eligible * education_config.credit_rate
        _append_breakdown(
            "education",
            (education, eligible, education_config.credit_rate),
            requested,
            note,
        )

    insurance_config = rules.insurance
    insurance = max(payload.deductions_insurance, 0.0)
    if insurance > 0:
        eligible = min(insurance, insurance_config.max_eligible_expense)
        note = None
        if insurance > insurance_config.max_eligible_expense:
            note = (
                "Life and health insurance premiums eligible for credits are capped at "
                f"€{insurance_config.max_eligible_expense:,.2f}."
            )
        requested = eligible * insurance_config.credit_rate
        _append_breakdown(
            "insurance",
            (insurance, eligible, insurance_config.credit_rate),
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


def _rounded_component_values(
    component: GeneralIncomeComponent,
) -> tuple[float, float, float, float, float]:
    gross_income = round_currency(component.gross_income)
    taxable_income = round_currency(component.taxable_income)
    tax_amount = round_currency(component.tax_after_credit)
    total_tax = round_currency(component.total_tax())
    net_income = round_currency(component.net_income())
    return gross_income, taxable_income, tax_amount, total_tax, net_income


def _add_deductible_expenses(detail: dict[str, Any], component: GeneralIncomeComponent) -> None:
    if component.deductible_expenses:
        detail["deductible_expenses"] = round_currency(component.deductible_expenses)


def _add_credit_fields(detail: dict[str, Any], component: GeneralIncomeComponent) -> None:
    if component.credit_eligible:
        detail["tax_before_credits"] = round_currency(component.tax_before_credit)
        detail["credits"] = round_currency(component.credit)


def _add_employment_contribution_fields(
    detail: dict[str, Any], component: GeneralIncomeComponent
) -> None:
    if component.category not in {"employment", "pension"}:
        return

    if component.employee_contributions:
        detail["employee_contributions"] = round_currency(
            component.employee_contributions
        )
        if component.employee_manual_contributions:
            detail["employee_contributions_manual"] = round_currency(
                component.employee_manual_contributions
            )
        if component.payments_per_year:
            detail["employee_contributions_per_payment"] = round_currency(
                component.employee_contributions / component.payments_per_year
            )

    if component.employer_contributions:
        detail["employer_contributions"] = round_currency(
            component.employer_contributions
        )
        if component.payments_per_year:
            detail["employer_contributions_per_payment"] = round_currency(
                component.employer_contributions / component.payments_per_year
            )


def _add_freelance_fields(
    detail: dict[str, Any], component: GeneralIncomeComponent, translator: Translator
) -> None:
    if component.category != "freelance":
        return

    detail["deductible_contributions"] = round_currency(component.contributions)
    detail["trade_fee"] = round_currency(component.trade_fee)
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
            detail[field] = round_currency(value)


def _add_payment_structure_fields(
    detail: dict[str, Any], component: GeneralIncomeComponent
) -> None:
    if component.monthly_gross_income is not None:
        detail["monthly_gross_income"] = round_currency(component.monthly_gross_income)

    if not component.payments_per_year:
        return

    detail["payments_per_year"] = component.payments_per_year

    gross_per_payment = component.gross_income_per_payment()
    if gross_per_payment is not None:
        detail["gross_income_per_payment"] = round_currency(gross_per_payment)

    net_per_payment = component.net_income_per_payment()
    if net_per_payment is not None:
        detail["net_income_per_payment"] = round_currency(net_per_payment)


def _add_deductions_field(detail: dict[str, Any], component: GeneralIncomeComponent) -> None:
    if component.deductions_applied:
        detail["deductions_applied"] = round_currency(component.deductions_applied)


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


__all__ = ["calculate_general_income_details"]
