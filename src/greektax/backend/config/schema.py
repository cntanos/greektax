"""Pydantic models describing the tax year configuration schema."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable, Mapping, Sequence

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    computed_field,
    field_validator,
    model_validator,
)
from typing_extensions import Self


class ConfigurationError(ValueError):
    """Raised when configuration values violate schema expectations."""


class ImmutableModel(BaseModel):
    """Base class that freezes instances and rejects unknown fields."""

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)


class TaxBracket(ImmutableModel):
    """Represents a single progressive tax bracket."""

    upper_bound: float | None = Field(default=None, alias="upper")
    rate: float
    pending_confirmation: bool = False
    estimate: bool = False

    @model_validator(mode="after")
    def _validate_values(self) -> TaxBracket:
        if self.rate < 0:
            raise ConfigurationError("Tax rates must be non-negative")
        if self.upper_bound is not None and self.upper_bound <= 0:
            raise ConfigurationError("Upper bounds must be positive values")
        return self


class HouseholdRateTable(ImmutableModel):
    """Structured rates for household brackets by dependant count."""

    dependants: Mapping[int, float]
    reduction_factor: float | None = None

    @field_validator("dependants", mode="before")
    @classmethod
    def _coerce_dependant_keys(cls, value: Any) -> Mapping[int, float]:
        if isinstance(value, Mapping):
            return {int(key): float(val) for key, val in value.items()}
        raise ConfigurationError("Household rate tables require dependant mappings")

    @model_validator(mode="after")
    def _validate_dependants(self) -> HouseholdRateTable:
        if not self.dependants:
            raise ConfigurationError("Household rate tables require dependant mappings")
        for dependant, rate in self.dependants.items():
            if dependant < 0:
                raise ConfigurationError("Dependant counts must be non-negative")
            if rate < 0:
                raise ConfigurationError("Dependant rates must be non-negative")
        if self.reduction_factor is not None and self.reduction_factor < 0:
            raise ConfigurationError(
                "Household rate reduction factors must be non-negative when provided"
            )
        return self

    def rate_for_dependants(self, dependants: int) -> float:
        if dependants in self.dependants:
            return self.dependants[dependants]
        ordered_counts = sorted(self.dependants)
        for count in ordered_counts:
            if dependants < count:
                return self.dependants[count]
        return self.dependants[ordered_counts[-1]]


class YouthRateTable(ImmutableModel):
    """Optional youth relief rates with dependant-aware overrides."""

    dependants: Mapping[int, float] = Field(default_factory=dict)
    rate: float | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_scalar(cls, data: Any) -> Mapping[str, Any]:
        if isinstance(data, Mapping):
            return data
        if data is None:
            return {}
        return {"rate": data}

    @field_validator("dependants", mode="before")
    @classmethod
    def _coerce_dependant_rates(cls, value: Any) -> Mapping[int, float]:
        if value is None:
            return {}
        if isinstance(value, Mapping):
            return {int(key): float(val) for key, val in value.items()}
        raise ConfigurationError("Youth dependant rates must be provided as a mapping")

    @model_validator(mode="after")
    def _validate_rates(self) -> YouthRateTable:
        if self.rate is not None and self.rate < 0:
            raise ConfigurationError("Youth rates must be non-negative")
        for dependant, rate in self.dependants.items():
            if dependant < 0:
                raise ConfigurationError("Youth dependant counts must be non-negative")
            if rate < 0:
                raise ConfigurationError("Youth dependant rates must be non-negative")
        if not self.dependants and self.rate is None:
            raise ConfigurationError(
                "Youth tables must define a base rate or dependant overrides"
            )
        return self

    def rate_for_dependants(self, dependants: int, household: HouseholdRateTable) -> float:
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


class MultiRateBracket(ImmutableModel):
    """Progressive bracket exposing household and youth rates."""

    upper_bound: float | None = Field(default=None, alias="upper")
    household: HouseholdRateTable
    youth_rates: Mapping[str, YouthRateTable] = Field(default_factory=dict)
    pending_confirmation: bool = False
    estimate: bool = False

    @model_validator(mode="before")
    @classmethod
    def _extract_rates(cls, data: Any) -> Mapping[str, Any]:
        if not isinstance(data, Mapping):
            raise ConfigurationError("Progressive bracket definitions must be mappings")

        prepared = dict(data)
        rates_section = prepared.pop("rates", None)
        if not isinstance(rates_section, Mapping):
            raise ConfigurationError("Progressive bracket 'rates' section is required")

        household = rates_section.get("household")
        if not isinstance(household, Mapping):
            raise ConfigurationError("Progressive bracket requires household rate definitions")
        prepared["household"] = household

        youth_section = rates_section.get("youth")
        if youth_section is not None:
            if not isinstance(youth_section, Mapping):
                raise ConfigurationError("Youth rates must be provided as a mapping")
            prepared["youth_rates"] = youth_section

        return prepared

    @field_validator("youth_rates", mode="before")
    @classmethod
    def _coerce_youth_rates(cls, value: Any) -> Mapping[str, Any]:
        if value is None:
            return {}
        if isinstance(value, Mapping):
            return {str(key): val for key, val in value.items()}
        raise ConfigurationError("Youth rate tables must be provided as a mapping")

    @model_validator(mode="after")
    def _validate_bounds(self) -> MultiRateBracket:
        if self.upper_bound is not None and self.upper_bound <= 0:
            raise ConfigurationError("Upper bounds must be positive values")
        return self

    @computed_field
    @property
    def rate(self) -> float:
        return self.household.rate_for_dependants(0)

    def rate_for_dependants(self, dependants: int) -> float:
        return self.household.rate_for_dependants(dependants)

    def youth_rate_for_dependants(self, category: str, dependants: int) -> float:
        table = self.youth_rates.get(category)
        if table is None:
            return self.household.rate_for_dependants(dependants)
        return table.rate_for_dependants(dependants, self.household)


ProgressiveTaxBracket = TaxBracket | MultiRateBracket


def _coerce_boolean(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value in {0, "0", "false", "False", None}:
        return False
    if value in {1, "1", "true", "True"}:
        return True
    raise ConfigurationError("Boolean flags must be explicit true/false values")


class EmploymentTaxCredit(ImmutableModel):
    """Year-specific reduction applied to employment income tax."""

    amounts_by_children: Mapping[int, float]
    incremental_amount_per_child: float = 0.0
    pending_confirmation: bool = False
    estimate: bool = False
    income_reduction_exempt_from_dependants: int | None = None

    @field_validator("amounts_by_children", mode="before")
    @classmethod
    def _coerce_amounts(cls, value: Any) -> Mapping[int, float]:
        if isinstance(value, Mapping):
            return {int(key): float(val) for key, val in value.items()}
        raise ConfigurationError("'amounts_by_children' must be a mapping")

    @field_validator("pending_confirmation", "estimate", mode="before")
    @classmethod
    def _coerce_flags(cls, value: Any) -> bool:
        return _coerce_boolean(value)

    @model_validator(mode="after")
    def _validate_values(self) -> EmploymentTaxCredit:
        for child_count, amount in self.amounts_by_children.items():
            if child_count < 0:
                raise ConfigurationError("Child counts must be non-negative")
            if amount < 0:
                raise ConfigurationError("Tax credit amounts must be non-negative")
        if self.incremental_amount_per_child < 0:
            raise ConfigurationError("Incremental amounts must be non-negative")
        if (
            self.income_reduction_exempt_from_dependants is not None
            and self.income_reduction_exempt_from_dependants < 0
        ):
            raise ConfigurationError(
                "'income_reduction_exempt_from_dependants' must be non-negative"
            )
        return self

    def amount_for_children(self, dependants: int) -> float:
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


class FamilyTaxCreditMetadata(ImmutableModel):
    """Metadata surfaced for the family tax credit presentation."""

    pending_confirmation: bool = False
    estimate: bool = False
    reduction_factor: float | None = None

    @field_validator("pending_confirmation", "estimate", mode="before")
    @classmethod
    def _coerce_flags(cls, value: Any) -> bool:
        return _coerce_boolean(value)

    @model_validator(mode="after")
    def _validate_reduction(self) -> FamilyTaxCreditMetadata:
        if self.reduction_factor is not None and self.reduction_factor < 0:
            raise ConfigurationError(
                "Family tax credit reduction_factor must be non-negative when provided"
            )
        return self


class PayrollConfig(ImmutableModel):
    """Supported payroll frequencies for an income category."""

    allowed_payments_per_year: Sequence[int]
    default_payments_per_year: int | None = None

    @field_validator("allowed_payments_per_year", mode="before")
    @classmethod
    def _coerce_allowed(cls, value: Any) -> Sequence[int]:
        if isinstance(value, Iterable):
            return tuple(int(entry) for entry in value)
        raise ConfigurationError(
            "Payroll configuration must define 'allowed_payments_per_year' as an iterable"
        )

    @model_validator(mode="after")
    def _validate_payroll(self) -> PayrollConfig:
        allowed = list(dict.fromkeys(self.allowed_payments_per_year))
        if not allowed:
            raise ConfigurationError("At least one payroll frequency must be provided")
        if any(entry <= 0 for entry in allowed):
            raise ConfigurationError("Allowed payroll frequencies must be positive integers")
        allowed.sort()
        default = self.default_payments_per_year if self.default_payments_per_year else allowed[-1]
        if default <= 0:
            raise ConfigurationError("Default payroll frequency must be a positive integer")
        if default not in allowed:
            raise ConfigurationError(
                "Default payroll frequency must be listed in the allowed set"
            )
        object.__setattr__(self, "allowed_payments_per_year", tuple(allowed))
        object.__setattr__(self, "default_payments_per_year", default)
        return self


class ContributionRates(ImmutableModel):
    """Employee and employer contribution rates for an income category."""

    employee_rate: float = 0.0
    employer_rate: float = 0.0
    monthly_salary_cap: float | None = None

    @model_validator(mode="after")
    def _validate_rates(self) -> ContributionRates:
        if self.employee_rate < 0:
            raise ConfigurationError("Contribution rates must be non-negative")
        if self.employer_rate < 0:
            raise ConfigurationError("Contribution rates must be non-negative")
        if self.monthly_salary_cap is not None and self.monthly_salary_cap < 0:
            raise ConfigurationError("Contribution salary caps must be non-negative")
        return self


class EmploymentConfig(ImmutableModel):
    """Configuration for salaried/pension income."""

    brackets: Sequence[ProgressiveTaxBracket] = Field(alias="tax_brackets")
    tax_credit: EmploymentTaxCredit
    payroll: PayrollConfig
    contributions: ContributionRates
    family_tax_credit: FamilyTaxCreditMetadata | None = None
    tekmiria_reduction_factor: float | None = None

    @field_validator("family_tax_credit", mode="before")
    @classmethod
    def _default_family_metadata(cls, value: Any) -> Any:
        if value is None:
            return {}
        return value

    @model_validator(mode="after")
    def _validate_config(self) -> EmploymentConfig:
        if not self.brackets:
            raise ConfigurationError("Employment configuration must include 'tax_brackets'")
        if self.tekmiria_reduction_factor is not None and self.tekmiria_reduction_factor < 0:
            raise ConfigurationError(
                "tekmiria_reduction_factor must be non-negative when provided"
            )
        metadata = self.family_tax_credit or FamilyTaxCreditMetadata(
            pending_confirmation=self.tax_credit.pending_confirmation,
            estimate=self.tax_credit.estimate,
        )
        object.__setattr__(self, "family_tax_credit", metadata)
        return self

    @computed_field
    @property
    def family_tax_credit_info(self) -> FamilyTaxCreditMetadata:
        return self.family_tax_credit or FamilyTaxCreditMetadata()

    @computed_field
    @property
    def tax_credit_metadata(self) -> FamilyTaxCreditMetadata:
        return self.family_tax_credit_info


class PensionConfig(ImmutableModel):
    """Configuration for pension income."""

    brackets: Sequence[ProgressiveTaxBracket] = Field(alias="tax_brackets")
    tax_credit: EmploymentTaxCredit
    payroll: PayrollConfig
    contributions: ContributionRates

    @model_validator(mode="after")
    def _validate_config(self) -> PensionConfig:
        if not self.brackets:
            raise ConfigurationError("Pension configuration must include 'tax_brackets'")
        return self


class TradeFeeSunset(ImmutableModel):
    """Represents a scheduled or proposed sunset for the trade fee."""

    status_key: str
    year: int | None = None
    description_key: str | None = None
    documentation_key: str | None = None
    documentation_url: str | None = None

    @model_validator(mode="after")
    def _validate_values(self) -> TradeFeeSunset:
        if self.year is not None and self.year <= 0:
            raise ConfigurationError("Trade fee sunset 'year' must be a positive integer")
        return self


class TradeFeeConfig(ImmutableModel):
    """Settings for the business activity fee (τέλος επιτηδεύματος)."""

    standard_amount: float
    reduced_amount: float | None = None
    newly_self_employed_reduction_years: int | None = None
    sunset: TradeFeeSunset | None = None
    fee_sunset: bool = False

    @field_validator("fee_sunset", mode="before")
    @classmethod
    def _coerce_flag(cls, value: Any) -> bool:
        return _coerce_boolean(value)

    @model_validator(mode="after")
    def _validate_amounts(self) -> TradeFeeConfig:
        if self.standard_amount < 0:
            raise ConfigurationError("'standard_amount' must be a non-negative number")
        if self.reduced_amount is not None and self.reduced_amount < 0:
            raise ConfigurationError("'reduced_amount' must be non-negative when provided")
        if (
            self.newly_self_employed_reduction_years is not None
            and self.newly_self_employed_reduction_years <= 0
        ):
            raise ConfigurationError(
                "'newly_self_employed_reduction_years' must be a positive integer"
            )
        return self


class EFKACategoryConfig(ImmutableModel):
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

    @field_validator("estimate", mode="before")
    @classmethod
    def _coerce_flag(cls, value: Any) -> bool:
        return _coerce_boolean(value)

    @model_validator(mode="after")
    def _validate_amounts(self) -> EFKACategoryConfig:
        if self.monthly_amount < 0:
            raise ConfigurationError("EFKA 'monthly_amount' must be non-negative")
        for field_name in (
            "auxiliary_monthly_amount",
            "pension_monthly_amount",
            "health_monthly_amount",
            "lump_sum_monthly_amount",
        ):
            value = getattr(self, field_name)
            if value is not None and value < 0:
                raise ConfigurationError(f"EFKA '{field_name}' must be non-negative")
        return self


class FreelanceConfig(ImmutableModel):
    """Configuration for freelance/business income."""

    brackets: Sequence[ProgressiveTaxBracket] = Field(alias="tax_brackets")
    trade_fee: TradeFeeConfig
    efka_categories: Sequence[EFKACategoryConfig] = Field(default_factory=tuple)
    pending_contribution_update: bool = False

    @field_validator("pending_contribution_update", mode="before")
    @classmethod
    def _coerce_flag(cls, value: Any) -> bool:
        return _coerce_boolean(value)

    @model_validator(mode="after")
    def _validate_config(self) -> FreelanceConfig:
        if not self.brackets:
            raise ConfigurationError("Freelance configuration must include 'tax_brackets'")
        return self


class AgriculturalConfig(ImmutableModel):
    """Configuration for agricultural income taxed on the progressive scale."""

    brackets: Sequence[ProgressiveTaxBracket] = Field(alias="tax_brackets")

    @model_validator(mode="after")
    def _validate_config(self) -> AgriculturalConfig:
        if not self.brackets:
            raise ConfigurationError(
                "Agricultural configuration must include 'tax_brackets'"
            )
        return self


class OtherIncomeConfig(ImmutableModel):
    """Configuration for other progressive income categories."""

    brackets: Sequence[ProgressiveTaxBracket] = Field(alias="tax_brackets")

    @model_validator(mode="after")
    def _validate_config(self) -> OtherIncomeConfig:
        if not self.brackets:
            raise ConfigurationError("Other income configuration must include 'tax_brackets'")
        return self


class RentalConfig(ImmutableModel):
    """Configuration for rental income."""

    brackets: Sequence[ProgressiveTaxBracket] = Field(alias="tax_brackets")

    @model_validator(mode="after")
    def _validate_config(self) -> RentalConfig:
        if not self.brackets:
            raise ConfigurationError("Rental configuration must include 'tax_brackets'")
        return self


class InvestmentConfig(ImmutableModel):
    """Configuration for investment income categories."""

    rates: Mapping[str, float]

    @field_validator("rates", mode="before")
    @classmethod
    def _coerce_rates(cls, value: Any) -> Mapping[str, float]:
        if not isinstance(value, Mapping):
            raise ConfigurationError("Investment configuration must include a 'rates' mapping")
        result = {str(key): float(rate) for key, rate in value.items()}
        if not result:
            raise ConfigurationError("Investment configuration requires at least one rate")
        return result


class DonationCreditConfig(ImmutableModel):
    """Configuration for donation tax credits."""

    credit_rate: float
    income_cap_rate: float | None = None

    @model_validator(mode="after")
    def _validate_rates(self) -> DonationCreditConfig:
        if self.credit_rate < 0 or self.credit_rate > 1:
            raise ConfigurationError("Donation credit rate must be between 0 and 1")
        if self.income_cap_rate is not None and not (0 <= self.income_cap_rate <= 1):
            raise ConfigurationError(
                "Donation income cap rate must be between 0 and 1 when provided"
            )
        return self


class MedicalCreditConfig(ImmutableModel):
    """Configuration for medical expense tax credits."""

    credit_rate: float
    income_threshold_rate: float
    max_credit: float

    @model_validator(mode="after")
    def _validate_rates(self) -> MedicalCreditConfig:
        if self.credit_rate < 0 or self.credit_rate > 1:
            raise ConfigurationError("Medical credit rate must be between 0 and 1")
        if self.income_threshold_rate < 0 or self.income_threshold_rate > 1:
            raise ConfigurationError(
                "Medical income threshold rate must be between 0 and 1"
            )
        if self.max_credit < 0:
            raise ConfigurationError("Medical max credit must be non-negative")
        return self


class CappedExpenseCreditConfig(ImmutableModel):
    """Configuration for credits with a capped eligible expense base."""

    credit_rate: float
    max_eligible_expense: float

    @model_validator(mode="after")
    def _validate_rates(self) -> CappedExpenseCreditConfig:
        if self.credit_rate < 0 or self.credit_rate > 1:
            raise ConfigurationError("Credit rate must be between 0 and 1")
        if self.max_eligible_expense < 0:
            raise ConfigurationError("Max eligible expense must be non-negative")
        return self


class DeductionThreshold(ImmutableModel):
    """Specific allowance thresholds exposed for deduction hints."""

    label_key: str
    amount: float | None = None
    percentage: float | None = None
    notes_key: str | None = None

    @model_validator(mode="after")
    def _validate_threshold(self) -> DeductionThreshold:
        if (
            self.amount is None
            and self.percentage is None
            and self.notes_key is None
        ):
            raise ConfigurationError(
                "Deduction thresholds require at least an amount, percentage, or notes"
            )
        if self.percentage is not None and not (0 <= self.percentage <= 1):
            raise ConfigurationError("Allowance percentages must be between 0 and 1")
        return self


class DeductionAllowance(ImmutableModel):
    """Structured allowance guidance for deduction hints."""

    label_key: str
    description_key: str | None = None
    thresholds: Sequence[DeductionThreshold] = Field(default_factory=tuple)


class DeductionRuleConfig(ImmutableModel):
    """Configuration block covering statutory deduction credit rules."""

    donations: DonationCreditConfig
    medical: MedicalCreditConfig
    education: CappedExpenseCreditConfig
    insurance: CappedExpenseCreditConfig


def _default_deduction_rules_payload() -> dict[str, dict[str, float]]:
    return {
        "donations": {"credit_rate": 0.20, "income_cap_rate": 0.10},
        "medical": {
            "credit_rate": 0.10,
            "income_threshold_rate": 0.05,
            "max_credit": 3_000.0,
        },
        "education": {"credit_rate": 0.10, "max_eligible_expense": 1_000.0},
        "insurance": {"credit_rate": 0.10, "max_eligible_expense": 1_200.0},
    }


class DeductionHint(ImmutableModel):
    """Hint metadata for user-facing deduction inputs."""

    id: str
    applies_to: Sequence[str] = Field(default_factory=tuple)
    label_key: str
    description_key: str | None = None
    input_id: str | None = None
    validation: Mapping[str, Any] = Field(default_factory=dict)
    allowances: Sequence[DeductionAllowance] = Field(default_factory=tuple)

    @field_validator("applies_to", mode="before")
    @classmethod
    def _coerce_applies_to(cls, value: Any) -> Sequence[str]:
        if value is None:
            return ()
        if isinstance(value, Iterable):
            return tuple(str(entry) for entry in value)
        raise ConfigurationError("'applies_to' must be an iterable of strings")

    @field_validator("allowances", mode="before")
    @classmethod
    def _coerce_allowances(cls, value: Any) -> Sequence[Mapping[str, Any]]:
        if value is None:
            return ()
        if isinstance(value, Iterable):
            return tuple(value)
        raise ConfigurationError("'allowances' must be an iterable when provided")

    @field_validator("validation", mode="before")
    @classmethod
    def _coerce_validation(cls, value: Any) -> Mapping[str, Any]:
        if value is None:
            return {}
        if isinstance(value, Mapping):
            return dict(value)
        raise ConfigurationError("'validation' must be a mapping when provided")


class DeductionConfig(ImmutableModel):
    """Container for deduction metadata hints."""

    hints: Sequence[DeductionHint] = Field(default_factory=tuple)
    rules: DeductionRuleConfig

    @model_validator(mode="before")
    @classmethod
    def _apply_defaults(cls, data: Any) -> Mapping[str, Any]:
        if data is None:
            data = {}
        if not isinstance(data, Mapping):
            raise ConfigurationError("'deductions' section must be a mapping")

        prepared = dict(data)
        hints = prepared.get("hints")
        if hints is None:
            prepared["hints"] = []

        rules = prepared.get("rules")
        defaults = _default_deduction_rules_payload()
        if rules is None:
            prepared["rules"] = defaults
        else:
            if not isinstance(rules, Mapping):
                raise ConfigurationError("'rules' must be a mapping when provided")
            merged = deepcopy(defaults)
            for key, value in rules.items():
                merged[key] = value
            prepared["rules"] = merged

        return prepared


class YearWarning(ImmutableModel):
    """Structured warning surfaced for a configured tax year."""

    id: str
    message_key: str
    severity: str = "info"
    applies_to: Sequence[str] = Field(default_factory=tuple)
    documentation_key: str | None = None
    documentation_url: str | None = None

    @field_validator("applies_to", mode="before")
    @classmethod
    def _coerce_applies_to(cls, value: Any) -> Sequence[str]:
        if value is None:
            return ()
        if isinstance(value, Iterable):
            return tuple(str(entry) for entry in value)
        raise ConfigurationError("Warning 'applies_to' must be an iterable when provided")

    @model_validator(mode="after")
    def _validate_severity(self) -> Self:
        if self.severity not in {"info", "warning", "error"}:
            raise ConfigurationError("Warning 'severity' must be one of: info, warning, error")
        return self


class DeductionDefaults(ImmutableModel):
    """Helper model bundling default deduction rule values."""

    donations: DonationCreditConfig
    medical: MedicalCreditConfig
    education: CappedExpenseCreditConfig
    insurance: CappedExpenseCreditConfig


class YearConfiguration(ImmutableModel):
    """Structured representation of a tax year configuration."""

    year: int
    meta: Mapping[str, Any] = Field(default_factory=dict)
    employment: EmploymentConfig
    pension: PensionConfig
    freelance: FreelanceConfig
    agricultural: AgriculturalConfig
    other: OtherIncomeConfig
    rental: RentalConfig
    investment: InvestmentConfig
    deductions: DeductionConfig
    warnings: Sequence[YearWarning] = Field(default_factory=tuple)

    @model_validator(mode="before")
    @classmethod
    def _flatten_income(cls, data: Any) -> Mapping[str, Any]:
        if not isinstance(data, Mapping):
            raise ConfigurationError("Configuration file must define a mapping at the top level")

        prepared = dict(data)
        meta = prepared.get("meta")
        if meta is None:
            prepared["meta"] = {}
        elif not isinstance(meta, Mapping):
            raise ConfigurationError("'meta' section must be a mapping if provided")

        income = prepared.pop("income", None)
        if not isinstance(income, Mapping):
            raise ConfigurationError("Configuration must include an 'income' section")

        required_sections = {
            "employment",
            "pension",
            "freelance",
            "agricultural",
            "other",
            "rental",
            "investment",
        }

        sections: dict[str, Mapping[str, Any]] = {}
        for section in required_sections:
            payload = income.get(section)
            if not isinstance(payload, Mapping):
                raise ConfigurationError(
                    f"Income configuration requires a '{section}' section"
                )
            sections[section] = dict(payload)

        employment = sections["employment"]
        pension = sections["pension"]
        if "tax_credit" not in pension and "tax_credit" in employment:
            pension["tax_credit"] = deepcopy(employment["tax_credit"])
        if "payroll" not in pension and "payroll" in employment:
            pension["payroll"] = deepcopy(employment["payroll"])

        prepared.update(sections)

        if "deductions" not in prepared:
            prepared["deductions"] = {}

        if "warnings" not in prepared or prepared["warnings"] is None:
            prepared["warnings"] = []

        return prepared

    @model_validator(mode="after")
    def _validate_year(self) -> YearConfiguration:
        progressive_sections = (
            self.employment.brackets,
            self.pension.brackets,
            self.freelance.brackets,
            self.agricultural.brackets,
            self.other.brackets,
            self.rental.brackets,
        )
        for brackets in progressive_sections:
            self._validate_bracket_sequence(brackets)
        return self

    @staticmethod
    def _validate_bracket_sequence(brackets: Sequence[ProgressiveTaxBracket]) -> None:
        if not brackets:
            raise ConfigurationError("At least one tax bracket must be defined")
        last_upper: float | None = None
        for bracket in brackets:
            upper = bracket.upper_bound
            if last_upper is not None and upper is not None and upper <= last_upper:
                raise ConfigurationError("Tax brackets must be in ascending order")
            last_upper = upper if upper is not None else last_upper
        if brackets[-1].upper_bound is not None:
            raise ConfigurationError("Final tax bracket must have an open upper bound")


class TaxYearManifestEntry(ImmutableModel):
    """Entry describing a supported tax year in the manifest."""

    year: int
    filename: str | None = None
    status: str = "active"
    notes_url: str | None = None

    @computed_field
    @property
    def resolved_filename(self) -> str:
        return self.filename or f"{self.year}.yaml"


class TaxYearManifest(ImmutableModel):
    """Manifest describing the available tax year configuration files."""

    years: Sequence[TaxYearManifestEntry]

    @model_validator(mode="after")
    def _validate_years(self) -> TaxYearManifest:
        seen: set[int] = set()
        for entry in self.years:
            if entry.year in seen:
                raise ConfigurationError(
                    f"Duplicate year {entry.year} declared in the configuration manifest"
                )
            seen.add(entry.year)
        return self

    def get_entry(self, year: int) -> TaxYearManifestEntry:
        for entry in self.years:
            if entry.year == year:
                return entry
        raise KeyError(year)

    @computed_field
    @property
    def supported_years(self) -> tuple[int, ...]:
        return tuple(sorted(entry.year for entry in self.years))


__all__ = [
    "AgriculturalConfig",
    "CappedExpenseCreditConfig",
    "ContributionRates",
    "DeductionAllowance",
    "DeductionConfig",
    "DeductionHint",
    "DeductionRuleConfig",
    "DeductionThreshold",
    "DonationCreditConfig",
    "EFKACategoryConfig",
    "EmploymentConfig",
    "EmploymentTaxCredit",
    "FamilyTaxCreditMetadata",
    "FreelanceConfig",
    "HouseholdRateTable",
    "ImmutableModel",
    "InvestmentConfig",
    "MedicalCreditConfig",
    "MultiRateBracket",
    "OtherIncomeConfig",
    "PayrollConfig",
    "PensionConfig",
    "ProgressiveTaxBracket",
    "RentalConfig",
    "TaxBracket",
    "TaxYearManifest",
    "TaxYearManifestEntry",
    "TradeFeeConfig",
    "TradeFeeSunset",
    "YearConfiguration",
    "YearWarning",
    "YouthRateTable",
    "ConfigurationError",
    "ValidationError",
]
