"""Data layer for annual tax configuration loaded from versioned YAML files.

Each tax year is described in declarative YAML, parsed into immutable
dataclasses that the calculation service and configuration API can share. The
module owns validation and caching so that adding a new year or tweaking rates
requires only configuration changes.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, MutableMapping, Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

CONFIG_DIRECTORY = Path(__file__).resolve().parent / "data"


class ConfigurationError(ValueError):
    """Raised when a configuration file fails validation."""


@dataclass(frozen=True)
class TaxBracket:
    """Represents a single progressive tax bracket."""

    upper_bound: float | None
    rate: float

    def __post_init__(self) -> None:  # pragma: no cover - defensive programming
        if self.rate < 0:
            raise ConfigurationError("Tax rates must be non-negative")
        if self.upper_bound is not None and self.upper_bound <= 0:
            raise ConfigurationError("Upper bounds must be positive values")


@dataclass(frozen=True)
class HouseholdRateTable:
    """Structured rates for household brackets by dependant count."""

    dependants: dict[int, float]
    reduction_factor: float | None = None

    def rate_for_dependants(self, dependants: int) -> float:
        """Return the applicable rate for ``dependants`` children."""

        if not self.dependants:
            raise ConfigurationError("Household rate tables require dependant mappings")

        if dependants in self.dependants:
            return self.dependants[dependants]

        ordered_counts = sorted(self.dependants)
        for count in ordered_counts:
            if dependants < count:
                return self.dependants[count]

        return self.dependants[ordered_counts[-1]]


@dataclass(frozen=True)
class YouthRateTable:
    """Optional youth relief rates with dependant-aware overrides."""

    dependants: dict[int, float] = field(default_factory=dict)
    rate: float | None = None

    def rate_for_dependants(self, dependants: int, household: HouseholdRateTable) -> float:
        """Return the youth rate for ``dependants`` falling back to household rates."""

        if self.dependants:
            ordered_counts = sorted(self.dependants)
            if dependants in self.dependants:
                return self.dependants[dependants]

            for count in ordered_counts:
                if dependants < count:
                    return self.dependants[count]

            return self.dependants[ordered_counts[-1]]

        if self.rate is not None:
            return self.rate

        return household.rate_for_dependants(dependants)


@dataclass(frozen=True)
class MultiRateBracket:
    """Progressive bracket exposing household and youth rates."""

    upper_bound: float | None
    household: HouseholdRateTable
    youth_rates: dict[str, YouthRateTable]
    pending_confirmation: bool = False
    estimate: bool = False

    @property
    def rate(self) -> float:
        """Fallback base rate compatible with single-rate calculations."""

        return self.household.rate_for_dependants(0)

    def rate_for_dependants(self, dependants: int) -> float:
        """Return the household rate for a dependant count."""

        return self.household.rate_for_dependants(dependants)

    def youth_rate_for_dependants(self, category: str, dependants: int) -> float:
        """Return the youth relief rate for ``category`` respecting dependant bands."""

        table = self.youth_rates.get(category)
        if table is None:
            return self.household.rate_for_dependants(dependants)

        return table.rate_for_dependants(dependants, self.household)


ProgressiveTaxBracket = TaxBracket | MultiRateBracket


def _parse_boolean_flag(value: Any, *, context: str) -> bool:
    """Coerce ``value`` into a boolean or raise a configuration error."""

    if value is None:
        return False
    if isinstance(value, bool):
        return value
    raise ConfigurationError(f"{context} must be provided as a boolean value")


@dataclass(frozen=True)
class EmploymentTaxCredit:
    """Year-specific reduction applied to employment income tax."""

    amounts_by_children: dict[int, float]
    incremental_amount_per_child: float
    pending_confirmation: bool = False
    estimate: bool = False

    def amount_for_children(self, dependants: int) -> float:
        """Return the tax credit amount for the provided dependant count."""

        if dependants < 0:
            return 0.0

        if dependants in self.amounts_by_children:
            return self.amounts_by_children[dependants]

        if not self.amounts_by_children:
            return 0.0

        max_key = max(self.amounts_by_children)
        base_amount = self.amounts_by_children[max_key]
        if dependants <= max_key:
            return base_amount

        extra_children = dependants - max_key
        return base_amount + extra_children * self.incremental_amount_per_child


@dataclass(frozen=True)
class FamilyTaxCreditMetadata:
    """Metadata surfaced for the family tax credit presentation."""

    pending_confirmation: bool = False
    estimate: bool = False
    reduction_factor: float | None = None


@dataclass(frozen=True)
class PayrollConfig:
    """Supported payroll frequencies for an income category."""

    allowed_payments_per_year: Sequence[int]
    default_payments_per_year: int


@dataclass(frozen=True)
class ContributionRates:
    """Employee and employer contribution rates for an income category."""

    employee_rate: float
    employer_rate: float
    monthly_salary_cap: float | None = None


@dataclass(frozen=True)
class EmploymentConfig:
    """Configuration for salaried/pension income."""

    brackets: Sequence[ProgressiveTaxBracket]
    tax_credit: EmploymentTaxCredit
    payroll: PayrollConfig
    contributions: ContributionRates
    family_tax_credit: FamilyTaxCreditMetadata = field(
        default_factory=FamilyTaxCreditMetadata
    )
    tekmiria_reduction_factor: float | None = None

    @property
    def family_tax_credit_info(self) -> FamilyTaxCreditMetadata:
        """Backwards compatible alias for metadata lookups."""

        return self.family_tax_credit

    @property
    def tax_credit_metadata(self) -> FamilyTaxCreditMetadata:
        """Alias maintained for callers expecting metadata naming."""

        return self.family_tax_credit


@dataclass(frozen=True)
class PensionConfig:
    """Configuration for pension income."""

    brackets: Sequence[ProgressiveTaxBracket]
    tax_credit: EmploymentTaxCredit
    payroll: PayrollConfig
    contributions: ContributionRates


@dataclass(frozen=True)
class TradeFeeSunset:
    """Represents a scheduled or proposed sunset for the trade fee."""

    status_key: str
    year: int | None
    description_key: str | None = None
    documentation_key: str | None = None
    documentation_url: str | None = None


@dataclass(frozen=True)
class TradeFeeConfig:
    """Settings for the business activity fee (τέλος επιτηδεύματος)."""

    standard_amount: float
    reduced_amount: float | None = None
    newly_self_employed_reduction_years: int | None = None
    sunset: TradeFeeSunset | None = None
    fee_sunset: bool = False


@dataclass(frozen=True)
class EFKACategoryConfig:
    """Configuration entry describing a freelancer EFKA contribution category."""

    id: str
    label_key: str
    monthly_amount: float
    auxiliary_monthly_amount: float | None = None
    description_key: str | None = None
    pension_monthly_amount: float | None = None
    health_monthly_amount: float | None = None
    lump_sum_monthly_amount: float | None = None
    estimate: bool = False


@dataclass(frozen=True)
class FreelanceConfig:
    """Configuration for freelance/business income."""

    brackets: Sequence[ProgressiveTaxBracket]
    trade_fee: TradeFeeConfig
    efka_categories: Sequence[EFKACategoryConfig]
    pending_contribution_update: bool = False


@dataclass(frozen=True)
class AgriculturalConfig:
    """Configuration for agricultural income taxed on the progressive scale."""

    brackets: Sequence[ProgressiveTaxBracket]


@dataclass(frozen=True)
class OtherIncomeConfig:
    """Configuration for other progressive income categories."""

    brackets: Sequence[ProgressiveTaxBracket]


@dataclass(frozen=True)
class RentalConfig:
    """Configuration for rental income."""

    brackets: Sequence[ProgressiveTaxBracket]


@dataclass(frozen=True)
class InvestmentConfig:
    """Configuration for investment income categories."""

    rates: dict[str, float]


@dataclass(frozen=True)
class DonationCreditConfig:
    """Configuration for donation tax credits."""

    credit_rate: float
    income_cap_rate: float | None = None

    def __post_init__(self) -> None:  # pragma: no cover - defensive validation
        if self.credit_rate < 0 or self.credit_rate > 1:
            raise ConfigurationError(
                "Donation credit rate must be between 0 and 1"
            )
        if self.income_cap_rate is not None:
            if self.income_cap_rate < 0 or self.income_cap_rate > 1:
                raise ConfigurationError(
                    "Donation income cap rate must be between 0 and 1 when provided"
                )


@dataclass(frozen=True)
class MedicalCreditConfig:
    """Configuration for medical expense tax credits."""

    credit_rate: float
    income_threshold_rate: float
    max_credit: float

    def __post_init__(self) -> None:  # pragma: no cover - defensive validation
        if self.credit_rate < 0 or self.credit_rate > 1:
            raise ConfigurationError(
                "Medical credit rate must be between 0 and 1"
            )
        if self.income_threshold_rate < 0 or self.income_threshold_rate > 1:
            raise ConfigurationError(
                "Medical income threshold rate must be between 0 and 1"
            )
        if self.max_credit < 0:
            raise ConfigurationError("Medical max credit must be non-negative")


@dataclass(frozen=True)
class CappedExpenseCreditConfig:
    """Configuration for credits with a capped eligible expense base."""

    credit_rate: float
    max_eligible_expense: float

    def __post_init__(self) -> None:  # pragma: no cover - defensive validation
        if self.credit_rate < 0 or self.credit_rate > 1:
            raise ConfigurationError(
                "Credit rate must be between 0 and 1"
            )
        if self.max_eligible_expense < 0:
            raise ConfigurationError(
                "Max eligible expense must be non-negative"
            )


@dataclass(frozen=True)
class DeductionRuleConfig:
    """Configuration block covering statutory deduction credit rules."""

    donations: DonationCreditConfig
    medical: MedicalCreditConfig
    education: CappedExpenseCreditConfig
    insurance: CappedExpenseCreditConfig


@dataclass(frozen=True)
class DeductionHint:
    """Hint metadata for user-facing deduction inputs."""

    id: str
    applies_to: Sequence[str]
    label_key: str
    description_key: str | None
    input_id: str | None
    validation: dict[str, Any]
    allowances: Sequence[DeductionAllowance]


@dataclass(frozen=True)
class DeductionThreshold:
    """Specific allowance thresholds exposed for deduction hints."""

    label_key: str
    amount: float | None
    percentage: float | None
    notes_key: str | None


@dataclass(frozen=True)
class DeductionAllowance:
    """Structured allowance guidance for deduction hints."""

    label_key: str
    description_key: str | None
    thresholds: Sequence[DeductionThreshold]


@dataclass(frozen=True)
class DeductionConfig:
    """Container for deduction metadata hints."""

    hints: Sequence[DeductionHint]
    rules: DeductionRuleConfig


@dataclass(frozen=True)
class YearWarning:
    """Structured warning surfaced for a configured tax year."""

    id: str
    message_key: str
    severity: str
    applies_to: Sequence[str]
    documentation_key: str | None = None
    documentation_url: str | None = None


@dataclass(frozen=True)
class YearConfiguration:
    """Structured representation of a tax year configuration."""

    year: int
    meta: dict[str, Any]
    employment: EmploymentConfig
    pension: PensionConfig
    freelance: FreelanceConfig
    agricultural: AgriculturalConfig
    other: OtherIncomeConfig
    rental: RentalConfig
    investment: InvestmentConfig
    deductions: DeductionConfig
    warnings: Sequence[YearWarning]


def _parse_progressive_brackets(
    brackets: Iterable[Mapping[str, Any]], *, year: int, context: str
) -> Sequence[ProgressiveTaxBracket]:
    parsed: list[ProgressiveTaxBracket] = []
    last_upper: float | None = None

    for index, bracket in enumerate(brackets, start=1):
        upper_raw = bracket.get("upper")
        upper_bound = float(upper_raw) if upper_raw is not None else None

        pending_confirmation = _parse_boolean_flag(
            bracket.get("pending_confirmation"),
            context=f"{context} bracket {index} 'pending_confirmation'",
        )
        estimate = _parse_boolean_flag(
            bracket.get("estimate"),
            context=f"{context} bracket {index} 'estimate'",
        )

        if "rates" in bracket:
            rates_raw = bracket["rates"]
            if not isinstance(rates_raw, Mapping):
                raise ConfigurationError(
                    f"{context} brackets must define 'rates' using a mapping"
                )

            household_raw = rates_raw.get("household")
            if not isinstance(household_raw, Mapping):
                raise ConfigurationError(
                    f"{context} brackets require a 'household' rate mapping"
                )

            dependants_raw = household_raw.get("dependants")
            if not isinstance(dependants_raw, Mapping) or not dependants_raw:
                raise ConfigurationError(
                    f"{context} household rates must define dependant mappings"
                )

            dependants: dict[int, float] = {}
            for key, value in dependants_raw.items():
                try:
                    dependant_count = int(key)
                except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
                    raise ConfigurationError(
                        f"{context} dependant keys must be integers"
                    ) from exc

                dependant_rate = float(value)
                if dependant_rate < 0:
                    raise ConfigurationError(
                        f"{context} dependant rates must be non-negative"
                    )

                dependants[dependant_count] = dependant_rate

            reduction_factor_raw = household_raw.get("reduction_factor")
            reduction_factor = (
                float(reduction_factor_raw)
                if reduction_factor_raw is not None
                else None
            )
            if reduction_factor is not None and reduction_factor < 0:
                raise ConfigurationError(
                    f"{context} household reduction factors must be non-negative"
                )

            youth_raw = rates_raw.get("youth")
            youth_rates: dict[str, YouthRateTable] = {}
            if youth_raw is not None:
                if not isinstance(youth_raw, Mapping):
                    raise ConfigurationError(
                        f"{context} youth rates must be provided as a mapping"
                    )
                for key, value in youth_raw.items():
                    youth_dependants: dict[int, float] = {}
                    base_rate: float | None = None

                    if isinstance(value, Mapping):
                        dependants_raw = value.get("dependants")
                        if dependants_raw is not None:
                            if not isinstance(dependants_raw, Mapping) or not dependants_raw:
                                raise ConfigurationError(
                                    f"{context} youth dependant rates must be provided as a mapping"
                                )
                            for dependant_key, dependant_value in dependants_raw.items():
                                try:
                                    dependant_count = int(dependant_key)
                                except (TypeError, ValueError) as exc:
                                    raise ConfigurationError(
                                        f"{context} youth dependant keys must be integers"
                                    ) from exc

                                dependant_rate = float(dependant_value)
                                if dependant_rate < 0:
                                    raise ConfigurationError(
                                        f"{context} youth dependant rates must be non-negative"
                                    )
                                youth_dependants[dependant_count] = dependant_rate

                        if "rate" in value and value["rate"] is not None:
                            base_rate = float(value["rate"])
                            if base_rate < 0:
                                raise ConfigurationError(
                                    f"{context} youth rates must be non-negative"
                                )
                    else:
                        base_rate = float(value)
                        if base_rate < 0:
                            raise ConfigurationError(
                                f"{context} youth rates must be non-negative"
                            )

                    if not youth_dependants and base_rate is None:
                        raise ConfigurationError(
                            f"{context} youth band '{key}' must define a base rate or dependant rates"
                        )

                    youth_rates[str(key)] = YouthRateTable(
                        dependants=youth_dependants,
                        rate=base_rate,
                    )

            if year >= 2026:
                required_dependants = {0, 1, 2, 3, 4}
                missing_dependants = required_dependants - dependants.keys()
                if missing_dependants:
                    missing_list = ", ".join(str(item) for item in sorted(missing_dependants))
                    raise ConfigurationError(
                        f"{context} bracket {index} missing dependant rate(s) for: {missing_list}"
                    )

                required_youth = {"under_25", "age26_30"}
                missing_youth = required_youth - youth_rates.keys()
                if missing_youth:
                    missing_list = ", ".join(sorted(missing_youth))
                    raise ConfigurationError(
                        f"{context} bracket {index} missing youth rate(s) for: {missing_list}"
                    )

                for band_name, youth_table in youth_rates.items():
                    if youth_table.dependants:
                        missing_dependants = required_dependants - youth_table.dependants.keys()
                        if missing_dependants:
                            missing_list = ", ".join(
                                str(item) for item in sorted(missing_dependants)
                            )
                            raise ConfigurationError(
                                f"{context} bracket {index} youth band '{band_name}' missing dependant rate(s) for: {missing_list}"
                            )

            bracket_obj: ProgressiveTaxBracket = MultiRateBracket(
                upper_bound=upper_bound,
                household=HouseholdRateTable(
                    dependants=dependants,
                    reduction_factor=reduction_factor,
                ),
                youth_rates=youth_rates,
                pending_confirmation=pending_confirmation,
                estimate=estimate,
            )

        elif "rate" in bracket:
            rate = float(bracket["rate"])
            bracket_obj = TaxBracket(upper_bound=upper_bound, rate=rate)
        else:
            raise ConfigurationError(
                f"{context} brackets must define either 'rate' or 'rates' entries"
            )

        if last_upper is not None and bracket_obj.upper_bound is not None:
            if bracket_obj.upper_bound <= last_upper:
                raise ConfigurationError("Tax brackets must be in ascending order")

        parsed.append(bracket_obj)
        last_upper = bracket_obj.upper_bound or last_upper

    if not parsed:
        raise ConfigurationError("At least one tax bracket must be defined")

    if parsed[-1].upper_bound is not None:
        raise ConfigurationError("Final tax bracket must have an open upper bound")

    return tuple(parsed)


def _parse_tax_credit(raw: Mapping[str, Any]) -> EmploymentTaxCredit:
    amounts_raw = raw.get("amounts_by_children")
    if not isinstance(amounts_raw, MutableMapping):
        raise ConfigurationError("'amounts_by_children' must be a mapping")

    amounts: dict[int, float] = {}
    for key, value in amounts_raw.items():
        child_count = int(key)
        amounts[child_count] = float(value)

    incremental = float(raw.get("incremental_amount_per_child", 0.0))
    pending = _parse_boolean_flag(
        raw.get("pending_confirmation"),
        context="employment.tax_credit 'pending_confirmation'",
    )
    estimate = _parse_boolean_flag(
        raw.get("estimate"),
        context="employment.tax_credit 'estimate'",
    )

    return EmploymentTaxCredit(
        amounts_by_children=amounts,
        incremental_amount_per_child=incremental,
        pending_confirmation=pending,
        estimate=estimate,
    )


def _parse_family_tax_credit_metadata(
    raw: Mapping[str, Any] | None,
    *,
    context: str,
    fallback_pending: bool,
    fallback_estimate: bool,
) -> FamilyTaxCreditMetadata:
    if raw is None:
        return FamilyTaxCreditMetadata(
            pending_confirmation=fallback_pending,
            estimate=fallback_estimate,
        )

    if not isinstance(raw, Mapping):
        raise ConfigurationError(f"{context} metadata must be a mapping")

    pending_value = raw.get("pending_confirmation")
    if pending_value is None:
        pending = fallback_pending
    else:
        pending = _parse_boolean_flag(
            pending_value,
            context=f"{context} 'pending_confirmation'",
        )

    estimate_value = raw.get("estimate")
    if estimate_value is None:
        estimate = fallback_estimate
    else:
        estimate = _parse_boolean_flag(
            estimate_value,
            context=f"{context} 'estimate'",
        )
    reduction_factor_raw = raw.get("reduction_factor")
    reduction_factor = (
        float(reduction_factor_raw)
        if reduction_factor_raw is not None
        else None
    )
    if reduction_factor is not None and reduction_factor < 0:
        raise ConfigurationError(
            f"{context} 'reduction_factor' must be non-negative when provided"
        )

    return FamilyTaxCreditMetadata(
        pending_confirmation=pending,
        estimate=estimate,
        reduction_factor=reduction_factor,
    )


def _parse_payroll_config(raw: Mapping[str, Any], context: str) -> PayrollConfig:
    if not isinstance(raw, Mapping):
        raise ConfigurationError(f"{context} payroll settings must be a mapping")

    allowed_raw = raw.get("allowed_payments_per_year")
    if not isinstance(allowed_raw, Iterable):
        raise ConfigurationError(
            f"{context} payroll must define 'allowed_payments_per_year' as an iterable"
        )

    allowed: list[int] = []
    for entry in allowed_raw:
        payments = int(entry)
        if payments <= 0:
            raise ConfigurationError("Allowed payroll frequencies must be positive integers")
        if payments not in allowed:
            allowed.append(payments)

    if not allowed:
        raise ConfigurationError("At least one payroll frequency must be provided")

    allowed.sort()

    default_raw = raw.get("default_payments_per_year")
    if default_raw is None:
        default = allowed[-1]
    else:
        default = int(default_raw)
        if default <= 0:
            raise ConfigurationError("Default payroll frequency must be a positive integer")

    if default not in allowed:
        raise ConfigurationError("Default payroll frequency must be listed in the allowed set")

    return PayrollConfig(
        allowed_payments_per_year=tuple(allowed),
        default_payments_per_year=default,
    )


def _parse_contribution_rates(
    raw: Mapping[str, Any] | None, context: str
) -> ContributionRates:
    if raw is None:
        return ContributionRates(employee_rate=0.0, employer_rate=0.0)

    if not isinstance(raw, Mapping):
        raise ConfigurationError(f"{context} contributions must be defined using a mapping")

    employee = float(raw.get("employee_rate", 0.0))
    employer = float(raw.get("employer_rate", 0.0))
    salary_cap_raw = raw.get("monthly_salary_cap")
    salary_cap = float(salary_cap_raw) if salary_cap_raw is not None else None

    if employee < 0 or employer < 0:
        raise ConfigurationError("Contribution rates must be non-negative")

    if salary_cap is not None and salary_cap < 0:
        raise ConfigurationError("Contribution salary caps must be non-negative")

    return ContributionRates(
        employee_rate=employee,
        employer_rate=employer,
        monthly_salary_cap=salary_cap,
    )


def _parse_employment_config(year: int, raw: Mapping[str, Any]) -> EmploymentConfig:
    brackets_raw = raw.get("tax_brackets")
    if not isinstance(brackets_raw, Iterable):
        raise ConfigurationError("Employment configuration must include 'tax_brackets'")

    credit_raw = raw.get("tax_credit")
    if not isinstance(credit_raw, Mapping):
        raise ConfigurationError("Employment configuration must include 'tax_credit'")

    payroll_raw = raw.get("payroll")
    if payroll_raw is None:
        raise ConfigurationError("Employment configuration must define payroll settings")

    contributions_raw = raw.get("contributions")

    tax_credit = _parse_tax_credit(credit_raw)

    family_credit_meta = _parse_family_tax_credit_metadata(
        raw.get("family_tax_credit"),
        context="employment.family_tax_credit",
        fallback_pending=tax_credit.pending_confirmation,
        fallback_estimate=tax_credit.estimate,
    )

    tekmiria_raw = raw.get("tekmiria_reduction_factor")
    tekmiria_reduction = (
        float(tekmiria_raw) if tekmiria_raw is not None else None
    )
    if tekmiria_reduction is not None and tekmiria_reduction < 0:
        raise ConfigurationError(
            "employment.tekmiria_reduction_factor must be non-negative when provided"
        )

    return EmploymentConfig(
        brackets=_parse_progressive_brackets(
            brackets_raw, year=year, context="employment.tax_brackets"
        ),
        tax_credit=tax_credit,
        payroll=_parse_payroll_config(payroll_raw, "Employment"),
        contributions=_parse_contribution_rates(contributions_raw, "Employment"),
        family_tax_credit=family_credit_meta,
        tekmiria_reduction_factor=tekmiria_reduction,
    )


def _parse_pension_config(
    year: int,
    raw: Mapping[str, Any],
    fallback_credit: EmploymentTaxCredit,
    fallback_payroll: PayrollConfig,
) -> PensionConfig:
    brackets_raw = raw.get("tax_brackets")
    if not isinstance(brackets_raw, Iterable):
        raise ConfigurationError("Pension configuration must include 'tax_brackets'")

    credit_raw = raw.get("tax_credit")
    if credit_raw is None:
        credit = fallback_credit
    else:
        if not isinstance(credit_raw, Mapping):
            raise ConfigurationError("Pension tax credit must be a mapping")
        credit = _parse_tax_credit(credit_raw)

    payroll_raw = raw.get("payroll")
    if payroll_raw is None:
        payroll = fallback_payroll
    else:
        payroll = _parse_payroll_config(payroll_raw, "Pension")

    contributions = _parse_contribution_rates(raw.get("contributions"), "Pension")

    return PensionConfig(
        brackets=_parse_progressive_brackets(
            brackets_raw, year=year, context="pension.tax_brackets"
        ),
        tax_credit=credit,
        payroll=payroll,
        contributions=contributions,
    )


def _parse_trade_fee(raw: Mapping[str, Any]) -> TradeFeeConfig:
    if "standard_amount" not in raw:
        raise ConfigurationError("Trade fee configuration requires 'standard_amount'")

    standard_amount = float(raw["standard_amount"])
    if standard_amount < 0:
        raise ConfigurationError("'standard_amount' must be a non-negative number")

    reduced_raw = raw.get("reduced_amount")
    reduced_amount = float(reduced_raw) if reduced_raw is not None else None
    if reduced_amount is not None and reduced_amount < 0:
        raise ConfigurationError("'reduced_amount' must be non-negative when provided")

    reduction_years_raw = raw.get("newly_self_employed_reduction_years")
    reduction_years = (
        int(reduction_years_raw) if reduction_years_raw is not None else None
    )
    if reduction_years is not None and reduction_years <= 0:
        raise ConfigurationError(
            "'newly_self_employed_reduction_years' must be a positive integer"
        )

    sunset_raw = raw.get("sunset")
    sunset: TradeFeeSunset | None = None
    if sunset_raw is not None:
        if not isinstance(sunset_raw, Mapping):
            raise ConfigurationError("'sunset' must be defined using a mapping when provided")

        status_key_raw = sunset_raw.get("status_key")
        if not status_key_raw or not isinstance(status_key_raw, str):
            raise ConfigurationError("Trade fee sunset requires a 'status_key' string")

        year_raw = sunset_raw.get("year")
        sunset_year = int(year_raw) if year_raw is not None else None
        if sunset_year is not None and sunset_year <= 0:
            raise ConfigurationError("Trade fee sunset 'year' must be a positive integer")

        description_key_raw = sunset_raw.get("description_key")
        if description_key_raw is not None and not isinstance(description_key_raw, str):
            raise ConfigurationError(
                "Trade fee sunset 'description_key' must be a string when provided"
            )

        documentation_key_raw = sunset_raw.get("documentation_key")
        if documentation_key_raw is not None and not isinstance(documentation_key_raw, str):
            raise ConfigurationError(
                "Trade fee sunset 'documentation_key' must be a string when provided"
            )

        documentation_url_raw = sunset_raw.get("documentation_url")
        if documentation_url_raw is not None and not isinstance(documentation_url_raw, str):
            raise ConfigurationError(
                "Trade fee sunset 'documentation_url' must be a string when provided"
            )

        sunset = TradeFeeSunset(
            status_key=status_key_raw,
            year=sunset_year,
            description_key=description_key_raw,
            documentation_key=documentation_key_raw,
            documentation_url=documentation_url_raw,
        )

    fee_sunset = _parse_boolean_flag(
        raw.get("fee_sunset"),
        context="freelance.trade_fee 'fee_sunset'",
    )

    return TradeFeeConfig(
        standard_amount=standard_amount,
        reduced_amount=reduced_amount,
        newly_self_employed_reduction_years=reduction_years,
        sunset=sunset,
        fee_sunset=fee_sunset,
    )


def _parse_efka_categories(
    raw: Iterable[Mapping[str, Any]] | None,
) -> Sequence[EFKACategoryConfig]:
    if not raw:
        return tuple()

    categories: list[EFKACategoryConfig] = []
    for entry in raw:
        if not isinstance(entry, Mapping):
            raise ConfigurationError("EFKA categories must be defined using mappings")

        category_id = entry.get("id")
        if not category_id or not isinstance(category_id, str):
            raise ConfigurationError("EFKA categories require a string 'id'")

        label_key = entry.get("label_key")
        if not label_key or not isinstance(label_key, str):
            raise ConfigurationError("EFKA categories require a 'label_key' string")

        monthly_amount = entry.get("monthly_amount")
        if monthly_amount is None:
            raise ConfigurationError("EFKA categories require 'monthly_amount'")

        monthly_value = float(monthly_amount)
        if monthly_value < 0:
            raise ConfigurationError("EFKA 'monthly_amount' must be non-negative")

        auxiliary_amount = entry.get("auxiliary_monthly_amount")
        auxiliary_value = (
            float(auxiliary_amount) if auxiliary_amount is not None else None
        )
        if auxiliary_value is not None and auxiliary_value < 0:
            raise ConfigurationError(
                "EFKA 'auxiliary_monthly_amount' must be non-negative when provided"
            )

        pension_amount = entry.get("pension_monthly_amount")
        pension_value = float(pension_amount) if pension_amount is not None else None
        if pension_value is not None and pension_value < 0:
            raise ConfigurationError(
                "EFKA 'pension_monthly_amount' must be non-negative when provided"
            )

        health_amount = entry.get("health_monthly_amount")
        health_value = float(health_amount) if health_amount is not None else None
        if health_value is not None and health_value < 0:
            raise ConfigurationError(
                "EFKA 'health_monthly_amount' must be non-negative when provided"
            )

        lump_sum_amount = entry.get("lump_sum_monthly_amount")
        lump_sum_value = (
            float(lump_sum_amount) if lump_sum_amount is not None else None
        )
        if lump_sum_value is not None and lump_sum_value < 0:
            raise ConfigurationError(
                "EFKA 'lump_sum_monthly_amount' must be non-negative when provided"
            )

        description_key = entry.get("description_key")
        if description_key is not None and not isinstance(description_key, str):
            raise ConfigurationError(
                "EFKA category 'description_key' must be a string when provided"
            )

        estimate = _parse_boolean_flag(
            entry.get("estimate"),
            context=f"freelance.efka_categories '{category_id}' estimate",
        )

        categories.append(
            EFKACategoryConfig(
                id=category_id,
                label_key=label_key,
                monthly_amount=monthly_value,
                auxiliary_monthly_amount=auxiliary_value,
                description_key=description_key,
                pension_monthly_amount=pension_value,
                health_monthly_amount=health_value,
                lump_sum_monthly_amount=lump_sum_value,
                estimate=estimate,
            )
        )

    return tuple(categories)


def _parse_freelance_config(year: int, raw: Mapping[str, Any]) -> FreelanceConfig:
    brackets_raw = raw.get("tax_brackets")
    if not isinstance(brackets_raw, Iterable):
        raise ConfigurationError("Freelance configuration must include 'tax_brackets'")

    trade_fee_raw = raw.get("trade_fee")
    if not isinstance(trade_fee_raw, Mapping):
        raise ConfigurationError("Freelance configuration must include 'trade_fee'")

    efka_categories_raw = raw.get("efka_categories")
    if efka_categories_raw is None:
        efka_categories: Sequence[EFKACategoryConfig] = tuple()
    elif not isinstance(efka_categories_raw, Iterable):
        raise ConfigurationError("'efka_categories' must be an iterable when provided")
    else:
        efka_categories = _parse_efka_categories(efka_categories_raw)

    pending_update = _parse_boolean_flag(
        raw.get("pending_contribution_update"),
        context="freelance.pending_contribution_update",
    )

    return FreelanceConfig(
        brackets=_parse_progressive_brackets(
            brackets_raw, year=year, context="freelance.tax_brackets"
        ),
        trade_fee=_parse_trade_fee(trade_fee_raw),
        efka_categories=efka_categories,
        pending_contribution_update=pending_update,
    )


def _parse_agricultural_config(year: int, raw: Mapping[str, Any]) -> AgriculturalConfig:
    brackets_raw = raw.get("tax_brackets")
    if not isinstance(brackets_raw, Iterable):
        raise ConfigurationError(
            "Agricultural configuration must include 'tax_brackets'"
        )

    return AgriculturalConfig(
        brackets=_parse_progressive_brackets(
            brackets_raw, year=year, context="agricultural.tax_brackets"
        )
    )


def _parse_other_income_config(year: int, raw: Mapping[str, Any]) -> OtherIncomeConfig:
    brackets_raw = raw.get("tax_brackets")
    if not isinstance(brackets_raw, Iterable):
        raise ConfigurationError("Other income configuration must include 'tax_brackets'")

    return OtherIncomeConfig(
        brackets=_parse_progressive_brackets(
            brackets_raw, year=year, context="other.tax_brackets"
        )
    )


def _parse_rental_config(year: int, raw: Mapping[str, Any]) -> RentalConfig:
    brackets_raw = raw.get("tax_brackets")
    if not isinstance(brackets_raw, Iterable):
        raise ConfigurationError("Rental configuration must include 'tax_brackets'")

    return RentalConfig(
        brackets=_parse_progressive_brackets(
            brackets_raw, year=year, context="rental.tax_brackets"
        )
    )


def _parse_investment_config(raw: Mapping[str, Any]) -> InvestmentConfig:
    rates_raw = raw.get("rates")
    if not isinstance(rates_raw, MutableMapping):
        raise ConfigurationError("Investment configuration must include a 'rates' mapping")

    rates: dict[str, float] = {}
    for key, value in rates_raw.items():
        rates[str(key)] = float(value)

    if not rates:
        raise ConfigurationError("Investment configuration requires at least one rate")

    return InvestmentConfig(rates=rates)


def _default_deduction_rules() -> DeductionRuleConfig:
    return DeductionRuleConfig(
        donations=DonationCreditConfig(credit_rate=0.20, income_cap_rate=0.10),
        medical=MedicalCreditConfig(
            credit_rate=0.10,
            income_threshold_rate=0.05,
            max_credit=3_000.0,
        ),
        education=CappedExpenseCreditConfig(
            credit_rate=0.10,
            max_eligible_expense=1_000.0,
        ),
        insurance=CappedExpenseCreditConfig(
            credit_rate=0.10,
            max_eligible_expense=1_200.0,
        ),
    )


def _parse_donation_credit(
    raw: Mapping[str, Any] | None, default: DonationCreditConfig
) -> DonationCreditConfig:
    if raw is None:
        return default
    if not isinstance(raw, Mapping):
        raise ConfigurationError("Deduction donation rules must be a mapping when provided")

    if "credit_rate" not in raw:
        raise ConfigurationError("Donation rules require a 'credit_rate'")

    credit_rate = float(raw["credit_rate"])
    income_cap_raw = raw.get("income_cap_rate")
    income_cap_rate = float(income_cap_raw) if income_cap_raw is not None else None

    return DonationCreditConfig(
        credit_rate=credit_rate,
        income_cap_rate=income_cap_rate,
    )


def _parse_medical_credit(
    raw: Mapping[str, Any] | None, default: MedicalCreditConfig
) -> MedicalCreditConfig:
    if raw is None:
        return default
    if not isinstance(raw, Mapping):
        raise ConfigurationError("Medical deduction rules must be a mapping when provided")

    required_fields = {"credit_rate", "income_threshold_rate", "max_credit"}
    missing = required_fields - set(raw)
    if missing:
        missing_list = ", ".join(sorted(missing))
        raise ConfigurationError(
            f"Medical deduction rules missing required field(s): {missing_list}"
        )

    return MedicalCreditConfig(
        credit_rate=float(raw["credit_rate"]),
        income_threshold_rate=float(raw["income_threshold_rate"]),
        max_credit=float(raw["max_credit"]),
    )


def _parse_capped_expense_credit(
    raw: Mapping[str, Any] | None, default: CappedExpenseCreditConfig, context: str
) -> CappedExpenseCreditConfig:
    if raw is None:
        return default
    if not isinstance(raw, Mapping):
        raise ConfigurationError(f"{context} deduction rules must be a mapping when provided")

    required_fields = {"credit_rate", "max_eligible_expense"}
    missing = required_fields - set(raw)
    if missing:
        missing_list = ", ".join(sorted(missing))
        raise ConfigurationError(
            f"{context} deduction rules missing required field(s): {missing_list}"
        )

    return CappedExpenseCreditConfig(
        credit_rate=float(raw["credit_rate"]),
        max_eligible_expense=float(raw["max_eligible_expense"]),
    )


def _parse_deduction_rules(
    raw: Mapping[str, Any] | None,
) -> DeductionRuleConfig:
    defaults = _default_deduction_rules()
    if raw is None:
        return defaults
    if not isinstance(raw, Mapping):
        raise ConfigurationError("'rules' must be a mapping when provided")

    donations = _parse_donation_credit(raw.get("donations"), defaults.donations)
    medical = _parse_medical_credit(raw.get("medical"), defaults.medical)
    education = _parse_capped_expense_credit(
        raw.get("education"), defaults.education, "Education"
    )
    insurance = _parse_capped_expense_credit(
        raw.get("insurance"), defaults.insurance, "Insurance"
    )

    return DeductionRuleConfig(
        donations=donations,
        medical=medical,
        education=education,
        insurance=insurance,
    )


def _parse_deduction_threshold(raw: Mapping[str, Any]) -> DeductionThreshold:
    label_key = raw.get("label_key")
    if not label_key or not isinstance(label_key, str):
        raise ConfigurationError("Deduction thresholds require a 'label_key' string")

    amount_raw = raw.get("amount")
    percentage_raw = raw.get("percentage")
    notes_key_raw = raw.get("notes_key")

    amount = float(amount_raw) if amount_raw is not None else None
    percentage = float(percentage_raw) if percentage_raw is not None else None
    if percentage is not None and not (0.0 <= percentage <= 1.0):
        raise ConfigurationError("Allowance percentages must be between 0 and 1")

    if (
        amount is None
        and percentage is None
        and notes_key_raw is None
    ):
        raise ConfigurationError(
            "Deduction thresholds require at least an amount, percentage, or notes"
        )

    if notes_key_raw is not None and not isinstance(notes_key_raw, str):
        raise ConfigurationError("Threshold 'notes_key' must be a string when provided")

    return DeductionThreshold(
        label_key=label_key,
        amount=amount,
        percentage=percentage,
        notes_key=notes_key_raw,
    )


def _parse_deduction_allowance(raw: Mapping[str, Any]) -> DeductionAllowance:
    label_key = raw.get("label_key")
    if not label_key or not isinstance(label_key, str):
        raise ConfigurationError("Deduction allowances require a 'label_key' string")

    description_key_raw = raw.get("description_key")
    if description_key_raw is not None and not isinstance(description_key_raw, str):
        raise ConfigurationError(
            "Deduction allowance 'description_key' must be a string when provided"
        )

    thresholds_raw = raw.get("thresholds", [])
    if thresholds_raw is None:
        thresholds_raw = []
    if not isinstance(thresholds_raw, Iterable):
        raise ConfigurationError("Deduction allowance 'thresholds' must be an iterable")

    thresholds = tuple(
        _parse_deduction_threshold(threshold)
        for threshold in thresholds_raw
    )

    return DeductionAllowance(
        label_key=label_key,
        description_key=description_key_raw,
        thresholds=thresholds,
    )


def _parse_deduction_hint(raw: Mapping[str, Any]) -> DeductionHint:
    hint_id = raw.get("id")
    if not hint_id or not isinstance(hint_id, str):
        raise ConfigurationError("Deduction hints require a string 'id'")

    applies_to_raw = raw.get("applies_to", [])
    if not isinstance(applies_to_raw, Iterable):
        raise ConfigurationError("'applies_to' must be an iterable of strings")
    applies_to = [str(entry) for entry in applies_to_raw]

    label_key_raw = raw.get("label_key")
    if not label_key_raw or not isinstance(label_key_raw, str):
        raise ConfigurationError("Deduction hints require a 'label_key' string")

    description_key_raw = raw.get("description_key")
    if description_key_raw is not None and not isinstance(description_key_raw, str):
        raise ConfigurationError("'description_key' must be a string when provided")

    input_id_raw = raw.get("input_id")
    if input_id_raw is not None and not isinstance(input_id_raw, str):
        raise ConfigurationError("'input_id' must be a string when provided")

    validation_raw = raw.get("validation", {})
    if validation_raw is None:
        validation_raw = {}
    if not isinstance(validation_raw, Mapping):
        raise ConfigurationError("'validation' must be a mapping when provided")

    allowances_raw = raw.get("allowances", [])
    if allowances_raw is None:
        allowances_raw = []
    if not isinstance(allowances_raw, Iterable):
        raise ConfigurationError("'allowances' must be an iterable when provided")

    allowances = tuple(
        _parse_deduction_allowance(allowance) for allowance in allowances_raw
    )

    return DeductionHint(
        id=str(hint_id),
        applies_to=tuple(applies_to),
        label_key=label_key_raw,
        description_key=description_key_raw,
        input_id=input_id_raw,
        validation=dict(validation_raw),
        allowances=allowances,
    )


def _parse_deductions_config(raw: Mapping[str, Any] | None) -> DeductionConfig:
    if raw is None:
        hints_raw: Iterable[Mapping[str, Any]] = []
        rules_raw: Mapping[str, Any] | None = None
    else:
        if not isinstance(raw, Mapping):
            raise ConfigurationError("'deductions' section must be a mapping")
        rules_raw = raw.get("rules")
        hints_candidate = raw.get("hints", [])
        if hints_candidate is None:
            hints_candidate = []
        if not isinstance(hints_candidate, Iterable):
            raise ConfigurationError("'hints' must be an iterable of hint definitions")
        hints_raw = hints_candidate

    rules = _parse_deduction_rules(rules_raw)
    hints = tuple(_parse_deduction_hint(hint) for hint in hints_raw)
    return DeductionConfig(hints=hints, rules=rules)


def _parse_year_warnings(
    raw: Iterable[Mapping[str, Any]] | None,
) -> Sequence[YearWarning]:
    if raw is None:
        return tuple()

    if not isinstance(raw, Iterable):
        raise ConfigurationError("'warnings' must be defined as an iterable when provided")

    warnings: list[YearWarning] = []
    for entry in raw:
        if not isinstance(entry, Mapping):
            raise ConfigurationError("Each warning definition must be a mapping")

        warning_id = entry.get("id")
        if not warning_id or not isinstance(warning_id, str):
            raise ConfigurationError("Warnings require a string 'id'")

        message_key = entry.get("message_key")
        if not message_key or not isinstance(message_key, str):
            raise ConfigurationError("Warnings require a 'message_key' string")

        severity_raw = entry.get("severity", "info")
        severity = str(severity_raw).lower()
        if severity not in {"info", "warning", "error"}:
            raise ConfigurationError(
                "Warning 'severity' must be one of: info, warning, error"
            )

        applies_to_raw = entry.get("applies_to", [])
        if applies_to_raw is None:
            applies_to_raw = []
        if not isinstance(applies_to_raw, Iterable):
            raise ConfigurationError(
                "Warning 'applies_to' must be an iterable when provided"
            )
        applies_to = tuple(str(item) for item in applies_to_raw)

        documentation_key_raw = entry.get("documentation_key")
        if documentation_key_raw is not None and not isinstance(documentation_key_raw, str):
            raise ConfigurationError(
                "Warning 'documentation_key' must be a string when provided"
            )

        documentation_url_raw = entry.get("documentation_url")
        if documentation_url_raw is not None and not isinstance(documentation_url_raw, str):
            raise ConfigurationError(
                "Warning 'documentation_url' must be a string when provided"
            )

        warnings.append(
            YearWarning(
                id=warning_id,
                message_key=message_key,
                severity=severity,
                applies_to=applies_to,
                documentation_key=documentation_key_raw,
                documentation_url=documentation_url_raw,
            )
        )

    return tuple(warnings)


def _parse_year_configuration(year: int, raw: Mapping[str, Any]) -> YearConfiguration:
    income_section = raw.get("income")
    if not isinstance(income_section, Mapping):
        raise ConfigurationError("Configuration must include an 'income' section")

    employment_raw = income_section.get("employment")
    if not isinstance(employment_raw, Mapping):
        raise ConfigurationError("Income configuration requires an 'employment' section")

    pension_raw = income_section.get("pension")
    if not isinstance(pension_raw, Mapping):
        raise ConfigurationError("Income configuration requires a 'pension' section")

    freelance_raw = income_section.get("freelance")
    if not isinstance(freelance_raw, Mapping):
        raise ConfigurationError("Income configuration requires a 'freelance' section")
    agricultural_raw = income_section.get("agricultural")
    if not isinstance(agricultural_raw, Mapping):
        raise ConfigurationError("Income configuration requires an 'agricultural' section")
    other_raw = income_section.get("other")
    if not isinstance(other_raw, Mapping):
        raise ConfigurationError("Income configuration requires an 'other' section")

    rental_raw = income_section.get("rental")
    if not isinstance(rental_raw, Mapping):
        raise ConfigurationError("Income configuration requires a 'rental' section")

    investment_raw = income_section.get("investment")
    if not isinstance(investment_raw, Mapping):
        raise ConfigurationError("Income configuration requires an 'investment' section")

    meta = raw.get("meta")
    if meta is None:
        meta = {}
    elif not isinstance(meta, Mapping):
        raise ConfigurationError("'meta' section must be a mapping if provided")

    config_year = raw.get("year")
    if config_year is not None and int(config_year) != year:
        raise ConfigurationError(
            f"Configuration year mismatch: expected {year}, found {config_year}"
        )

    employment_config = _parse_employment_config(year, employment_raw)

    return YearConfiguration(
        year=year,
        meta=dict(meta),
        employment=employment_config,
        pension=_parse_pension_config(
            year,
            pension_raw,
            employment_config.tax_credit,
            employment_config.payroll,
        ),
        freelance=_parse_freelance_config(year, freelance_raw),
        agricultural=_parse_agricultural_config(year, agricultural_raw),
        other=_parse_other_income_config(year, other_raw),
        rental=_parse_rental_config(year, rental_raw),
        investment=_parse_investment_config(investment_raw),
        deductions=_parse_deductions_config(raw.get("deductions")),
        warnings=_parse_year_warnings(raw.get("warnings")),
    )


@lru_cache(maxsize=8)
def load_year_configuration(year: int) -> YearConfiguration:
    """Load configuration for the specified tax year from disk."""

    config_file = CONFIG_DIRECTORY / f"{year}.yaml"
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration for year {year} not found")

    with config_file.open("r", encoding="utf-8") as handle:
        raw_config = yaml.safe_load(handle) or {}

    if not isinstance(raw_config, Mapping):
        raise ConfigurationError("Configuration file must define a mapping at the top level")

    return _parse_year_configuration(year, raw_config)


def available_years() -> Sequence[int]:
    """Return a sorted collection of tax years with configuration files."""

    years: set[int] = set()
    for path in CONFIG_DIRECTORY.glob("*.yaml"):
        try:
            years.add(int(path.stem))
        except ValueError:  # pragma: no cover - non-numeric filenames are ignored defensively
            continue

    return tuple(sorted(years))
