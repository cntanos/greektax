"""Typed request/response models shared across the calculation services.

The refactor moved the calculation pipeline away from transient, per-module
dataclasses and towards a cohesive set of Pydantic inputs with lightweight
dataclasses for derived results. Centralising the schema here keeps validation,
normalisation, and downstream serialisation in sync for routes, background
tasks, and any future integrations.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .api import (
    AgriculturalIncomeInput,
    CalculationRequest,
    CalculationResponse,
    DeductionBreakdownEntry,
    DeductionsInput,
    DetailEntry,
    DependentsInput,
    DemographicsInput,
    EmploymentInput,
    FreelanceInput,
    PensionInput,
    RentalInput,
    ObligationsInput,
    OtherIncomeInput,
    ResponseMeta,
    Summary,
    SummaryLabels,
    format_validation_error,
    NET_INCOME_INPUT_ERROR,
)

__all__ = [
    "CalculationInput",
    "GeneralIncomeComponent",
    "DetailTotals",
    "CalculationRequest",
    "CalculationResponse",
    "DependentsInput",
    "DemographicsInput",
    "EmploymentInput",
    "PensionInput",
    "FreelanceInput",
    "RentalInput",
    "AgriculturalIncomeInput",
    "OtherIncomeInput",
    "ObligationsInput",
    "DeductionsInput",
    "DeductionBreakdownEntry",
    "SummaryLabels",
    "Summary",
    "DetailEntry",
    "ResponseMeta",
    "format_validation_error",
    "NET_INCOME_INPUT_ERROR",
]


class CalculationInput(BaseModel):
    """Validated and normalised user input for tax calculations."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    year: int
    locale: str
    children: int
    employment_income: float
    employment_monthly_income: float | None
    employment_payments_per_year: int | None
    employment_manual_contributions: float
    employment_include_social_contributions: bool
    employment_include_employee_contributions: bool
    employment_include_manual_contributions: bool
    employment_include_employer_contributions: bool
    withholding_tax: float
    pension_income: float
    pension_monthly_income: float | None
    pension_payments_per_year: int | None
    freelance_profit: float
    freelance_gross_revenue: float
    freelance_deductible_expenses: float
    freelance_category_id: str | None
    freelance_category_months: int | None
    freelance_category_contribution: float
    freelance_additional_contributions: float
    freelance_auxiliary_contributions: float
    freelance_lump_sum_contributions: float
    freelance_include_category_contributions: bool
    freelance_include_mandatory_contributions: bool
    freelance_include_auxiliary_contributions: bool
    freelance_include_lump_sum_contributions: bool
    include_trade_fee: bool
    freelance_trade_fee_location: str
    freelance_years_active: int | None
    freelance_newly_self_employed: bool
    rental_gross_income: float
    rental_deductible_expenses: float
    investment_amounts: Mapping[str, float]
    enfia_due: float
    luxury_due: float
    agricultural_gross_revenue: float
    agricultural_deductible_expenses: float
    agricultural_professional_farmer: bool
    other_taxable_income: float
    deductions_donations: float
    deductions_medical: float
    deductions_education: float
    deductions_insurance: float
    toggles: Mapping[str, bool] = Field(default_factory=dict)
    taxpayer_birth_year: int | None = None
    taxpayer_age_band: str | None = None
    youth_employment_override: str | None = None
    small_village: bool = False
    new_mother: bool = False

    @property
    def freelance_taxable_income(self) -> float:
        taxable = self.freelance_profit - self.total_freelance_contributions
        return taxable if taxable > 0 else 0.0

    @property
    def total_freelance_contributions(self) -> float:
        return (
            self.freelance_effective_category_contribution
            + self.freelance_effective_mandatory_contribution
            + self.freelance_effective_auxiliary_contribution
            + self.freelance_effective_lump_sum_contribution
        )

    @property
    def freelance_total_contributions(self) -> float:
        """Maintain backwards-compatible naming for total contributions."""

        return self.total_freelance_contributions

    @property
    def freelance_effective_category_contribution(self) -> float:
        if not self.freelance_include_category_contributions:
            return 0.0
        return self.freelance_category_contribution

    @property
    def freelance_effective_mandatory_contribution(self) -> float:
        if not self.freelance_include_mandatory_contributions:
            return 0.0
        return self.freelance_additional_contributions

    @property
    def freelance_effective_auxiliary_contribution(self) -> float:
        if not self.freelance_include_auxiliary_contributions:
            return 0.0
        return self.freelance_auxiliary_contributions

    @property
    def freelance_effective_lump_sum_contribution(self) -> float:
        if not self.freelance_include_lump_sum_contributions:
            return 0.0
        return self.freelance_lump_sum_contributions

    @property
    def has_employment_income(self) -> bool:
        return self.employment_income > 0

    @property
    def has_pension_income(self) -> bool:
        return self.pension_income > 0

    @property
    def has_freelance_income(self) -> bool:
        """Alias for ``has_freelance_activity`` expected by legacy callers."""

        return self.has_freelance_activity

    @property
    def has_freelance_activity(self) -> bool:
        return (
            self.freelance_profit > 0
            or self.total_freelance_contributions > 0
            or self.freelance_taxable_income > 0
        )

    @property
    def agricultural_profit(self) -> float:
        profit = self.agricultural_gross_revenue - self.agricultural_deductible_expenses
        return profit if profit > 0 else 0.0

    @property
    def agricultural_taxable_income(self) -> float:
        """Alias for legacy agricultural taxable income naming."""

        return self.agricultural_profit

    @property
    def has_agricultural_income(self) -> bool:
        return (
            self.agricultural_gross_revenue > 0
            or self.agricultural_deductible_expenses > 0
            or self.agricultural_profit > 0
        )

    @property
    def has_non_agricultural_taxable_income(self) -> bool:
        return any(
            (
                self.has_employment_income,
                self.has_pension_income,
                self.freelance_taxable_income > 0,
                self.other_taxable_income > 0,
                self.rental_taxable_income > 0,
                self.has_investment_income,
            )
        )

    @property
    def qualifies_for_agricultural_tax_credit(self) -> bool:
        if not self.has_agricultural_income:
            return False
        if self.agricultural_professional_farmer:
            return True
        return not self.has_non_agricultural_taxable_income

    @property
    def has_other_income(self) -> bool:
        return self.other_taxable_income > 0

    @property
    def total_deductions(self) -> float:
        total = (
            self.deductions_donations
            + self.deductions_medical
            + self.deductions_education
            + self.deductions_insurance
        )
        return total if total > 0 else 0.0

    def model_post_init(self, __context: Any) -> None:  # type: ignore[override]
        object.__setattr__(self, "toggles", MappingProxyType(dict(self.toggles)))

    def toggle_enabled(self, key: str) -> bool:
        value = self.toggles.get(key)
        return bool(value) if value is not None else False

    @property
    def taxpayer_age(self) -> int | None:
        if self.taxpayer_birth_year is None:
            return None
        age = self.year - self.taxpayer_birth_year
        return age if age >= 0 else None

    @property
    def youth_rate_category(self) -> str | None:
        override = self.youth_employment_override
        if override:
            return override

        if not self.toggle_enabled("youth_eligibility"):
            return None

        if self.taxpayer_age_band in {"under_25", "age26_30"}:
            return self.taxpayer_age_band

        age = self.taxpayer_age
        if age is None:
            return None
        if age < 25:
            return "under_25"
        if age <= 30:
            return "age26_30"
        return None

    @property
    def youth_relief_applied(self) -> bool:
        return self.youth_rate_category is not None

    @property
    def rental_taxable_income(self) -> float:
        taxable = self.rental_gross_income - self.rental_deductible_expenses
        return taxable if taxable > 0 else 0.0

    @property
    def has_rental_income(self) -> bool:
        return (
            self.rental_gross_income > 0
            or self.rental_deductible_expenses > 0
            or self.rental_taxable_income > 0
        )

    @property
    def has_investment_income(self) -> bool:
        return any(amount > 0 for amount in self.investment_amounts.values())

    @property
    def presumptive_adjustments(self) -> tuple[str, ...]:
        if not self.toggle_enabled("presumptive_relief"):
            return tuple()

        adjustments: list[str] = []
        if self.small_village:
            adjustments.append("small_village")
        if self.new_mother:
            adjustments.append("new_mother")
        return tuple(adjustments)

    @property
    def presumptive_relief_applied(self) -> bool:
        if not self.toggle_enabled("tekmiria_reduction"):
            return False
        return bool(self.presumptive_adjustments)

    @property
    def has_enfia_obligation(self) -> bool:
        return self.enfia_due > 0

    @property
    def has_luxury_obligation(self) -> bool:
        return self.luxury_due > 0


@dataclass(slots=True)
class GeneralIncomeComponent:
    """Represents an income category that shares the progressive scale."""

    category: str
    label_key: str
    gross_income: float
    taxable_income: float
    credit_eligible: bool
    contributions: float = 0.0
    deductible_expenses: float = 0.0
    trade_fee: float = 0.0
    tax_before_credit: float = 0.0
    credit: float = 0.0
    tax_after_credit: float = 0.0
    payments_per_year: int | None = None
    monthly_gross_income: float | None = None
    employee_contributions: float = 0.0
    employee_manual_contributions: float = 0.0
    employer_contributions: float = 0.0
    include_employee_contributions: bool = True
    category_contributions: float = 0.0
    additional_contributions: float = 0.0
    auxiliary_contributions: float = 0.0
    lump_sum_contributions: float = 0.0
    deductions_applied: float = 0.0

    def total_tax(self) -> float:
        total = self.tax_after_credit
        if self.category == "freelance":
            total += self.trade_fee
        return total

    def net_income(self) -> float:
        net = self.gross_income - self.tax_after_credit
        if self.category == "freelance":
            net -= self.contributions + self.trade_fee
        if (
            self.category in {"employment", "pension"}
            and self.include_employee_contributions
        ):
            net -= self.employee_contributions
        return net

    def net_income_per_payment(self) -> float | None:
        if not self.payments_per_year or self.payments_per_year <= 0:
            return None
        return self.net_income() / self.payments_per_year

    def gross_income_per_payment(self) -> float | None:
        if not self.payments_per_year or self.payments_per_year <= 0:
            return None
        return self.gross_income / self.payments_per_year

    def employer_cost(self) -> float:
        return self.gross_income + self.employer_contributions

    def employer_cost_per_payment(self) -> float | None:
        if not self.payments_per_year or self.payments_per_year <= 0:
            return None
        return self.employer_cost() / self.payments_per_year


@dataclass(slots=True)
class DetailTotals:
    """Tracks cumulative totals for calculation results."""

    income: float = 0.0
    tax: float = 0.0
    net: float = 0.0
    taxable: float = 0.0

    def add(
        self,
        income: float = 0.0,
        tax: float = 0.0,
        net: float = 0.0,
        taxable: float = 0.0,
    ) -> None:
        self.income += income
        self.tax += tax
        self.net += net
        self.taxable += taxable

    def merge(self, other: DetailTotals) -> None:
        self.income += other.income
        self.tax += other.tax
        self.net += other.net
        self.taxable += other.taxable
