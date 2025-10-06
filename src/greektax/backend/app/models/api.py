"""Pydantic models describing the public API surface."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_validator,
)

__all__ = [
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
    "CalculationRequest",
    "DeductionBreakdownEntry",
    "SummaryLabels",
    "Summary",
    "DetailEntry",
    "ResponseMeta",
    "CalculationResponse",
    "format_validation_error",
    "NET_INCOME_INPUT_ERROR",
]


NET_INCOME_INPUT_ERROR = (
    "Employment net income inputs are no longer supported; provide gross amounts instead"
)


class DependentsInput(BaseModel):
    """Household dependent information supplied by the user."""

    model_config = ConfigDict(extra="forbid")

    children: int = Field(default=0, ge=0, le=15)


class DemographicsInput(BaseModel):
    """Basic taxpayer demographics used for relief eligibility."""

    model_config = ConfigDict(extra="forbid")

    taxpayer_birth_year: int | None = Field(default=None, ge=1901, le=2100)
    birth_year: int = Field(..., ge=1901, le=2100)
    small_village: bool = False
    new_mother: bool = False

    @model_validator(mode="before")
    @classmethod
    def _ensure_birth_year(cls, data: Any) -> Any:
        if not isinstance(data, Mapping):
            return data

        if "birth_year" not in data and "taxpayer_birth_year" in data:
            copied = dict(data)
            copied["birth_year"] = copied.get("taxpayer_birth_year")
            return copied
        return data

    @staticmethod
    def _normalise_boolean_flags(value: Any) -> bool:
        if value is None:
            return False
        return bool(value)

    @field_validator("small_village", "new_mother", mode="before")
    @classmethod
    def _coerce_boolean_flags(cls, value: Any) -> bool:
        return cls._normalise_boolean_flags(value)

    @model_validator(mode="after")
    def _align_birth_year_aliases(self) -> "DemographicsInput":
        birth_year = self.birth_year or self.taxpayer_birth_year
        if self.taxpayer_birth_year is not None and self.taxpayer_birth_year != birth_year:
            raise ValueError(
                "birth_year and taxpayer_birth_year must match when both are provided"
            )
        object.__setattr__(self, "birth_year", birth_year)
        object.__setattr__(self, "taxpayer_birth_year", birth_year)
        return self


class EmploymentInput(BaseModel):
    """Employment income and withholding information."""

    model_config = ConfigDict(extra="forbid")

    gross_income: float = Field(default=0.0, ge=0)
    monthly_income: float | None = Field(default=None, ge=0)
    net_income: float | None = Field(default=None, ge=0)
    net_monthly_income: float | None = Field(default=None, ge=0)
    payments_per_year: int | None = Field(default=None, ge=0)
    employee_contributions: float = Field(default=0.0, ge=0)
    include_social_contributions: bool = True
    include_employee_contributions: bool = True
    include_manual_employee_contributions: bool = True
    include_employer_contributions: bool = True

    @field_validator("net_income", "net_monthly_income")
    @classmethod
    def _reject_net_income(cls, value: float | None) -> float | None:
        if value is not None and value > 0:
            raise ValueError(NET_INCOME_INPUT_ERROR)
        return value

    @model_validator(mode="after")
    def _synchronise_contribution_flags(self) -> "EmploymentInput":
        fields_set = getattr(self, "model_fields_set", set())
        if "include_social_contributions" in fields_set:
            base = bool(self.include_social_contributions)
            if "include_employee_contributions" not in fields_set:
                object.__setattr__(self, "include_employee_contributions", base)
            if "include_manual_employee_contributions" not in fields_set:
                object.__setattr__(
                    self, "include_manual_employee_contributions", base
                )
            if "include_employer_contributions" not in fields_set:
                object.__setattr__(self, "include_employer_contributions", base)
        else:
            combined = (
                bool(self.include_employee_contributions)
                or bool(self.include_manual_employee_contributions)
                or bool(self.include_employer_contributions)
            )
            object.__setattr__(self, "include_social_contributions", combined)
        return self


class PensionInput(BaseModel):
    """Pension income details."""

    model_config = ConfigDict(extra="forbid")

    gross_income: float = Field(default=0.0, ge=0)
    monthly_income: float | None = Field(default=None, ge=0)
    payments_per_year: int | None = Field(default=None, ge=0)


class FreelanceInput(BaseModel):
    """Freelance and self-employment inputs."""

    model_config = ConfigDict(extra="forbid")

    profit: float | None = Field(default=None, ge=0)
    gross_revenue: float = Field(default=0.0, ge=0)
    deductible_expenses: float = Field(default=0.0, ge=0)
    efka_category: str | None = None
    efka_months: int | None = Field(default=None, ge=0)
    mandatory_contributions: float = Field(default=0.0, ge=0)
    auxiliary_contributions: float = Field(default=0.0, ge=0)
    lump_sum_contributions: float = Field(default=0.0, ge=0)
    include_trade_fee: bool = True
    include_category_contributions: bool = True
    include_mandatory_contributions: bool = True
    include_auxiliary_contributions: bool = True
    include_lump_sum_contributions: bool = True
    trade_fee_location: str = "standard"
    years_active: int | None = Field(default=None, ge=0)
    newly_self_employed: bool = False

    @field_validator(
        "include_trade_fee",
        "newly_self_employed",
        "include_category_contributions",
        "include_mandatory_contributions",
        "include_auxiliary_contributions",
        "include_lump_sum_contributions",
        mode="before",
    )
    @classmethod
    def _normalise_optional_bool(cls, value: Any, info: ValidationInfo) -> bool:
        if value is None:
            defaults = {
                "include_trade_fee": True,
                "include_category_contributions": True,
                "include_mandatory_contributions": True,
                "include_auxiliary_contributions": True,
                "include_lump_sum_contributions": True,
                "newly_self_employed": False,
            }
            return defaults.get(info.field_name, False)
        return bool(value)

    @field_validator("trade_fee_location", mode="before")
    @classmethod
    def _normalise_trade_fee_location(cls, value: Any) -> str:
        if value is None:
            return "standard"
        if isinstance(value, str):
            normalised = value.strip().lower()
            if normalised in {"", "standard"}:
                return "standard"
            if normalised == "reduced":
                return "reduced"
        raise ValueError("Invalid trade fee location selection")


class RentalInput(BaseModel):
    """Rental income entries."""

    model_config = ConfigDict(extra="forbid")

    gross_income: float = Field(default=0.0, ge=0)
    deductible_expenses: float = Field(default=0.0, ge=0)


class AgriculturalIncomeInput(BaseModel):
    """Agricultural activity data."""

    model_config = ConfigDict(extra="forbid")

    gross_revenue: float = Field(default=0.0, ge=0)
    deductible_expenses: float = Field(default=0.0, ge=0)
    professional_farmer: bool = False


class DeductionsInput(BaseModel):
    """Tax relief inputs provided by the user."""

    model_config = ConfigDict(extra="forbid")

    donations: float = Field(default=0.0, ge=0)
    medical: float = Field(default=0.0, ge=0)
    education: float = Field(default=0.0, ge=0)
    insurance: float = Field(default=0.0, ge=0)


class OtherIncomeInput(BaseModel):
    """Miscellaneous taxable income outside defined categories."""

    model_config = ConfigDict(extra="forbid")

    taxable_income: float = Field(default=0.0, ge=0)


class ObligationsInput(BaseModel):
    """Additional annual obligations (ENFIA, luxury tax)."""

    model_config = ConfigDict(extra="forbid")

    enfia: float = Field(default=0.0, ge=0)
    luxury: float = Field(default=0.0, ge=0)


class CalculationRequest(BaseModel):
    """Complete payload accepted by the calculation endpoint."""

    model_config = ConfigDict(extra="forbid")

    year: int = Field(..., ge=0)
    locale: str = Field(default="en")
    dependents: DependentsInput = Field(default_factory=DependentsInput)
    demographics: DemographicsInput
    employment: EmploymentInput = Field(default_factory=EmploymentInput)
    pension: PensionInput = Field(default_factory=PensionInput)
    freelance: FreelanceInput = Field(default_factory=FreelanceInput)
    rental: RentalInput = Field(default_factory=RentalInput)
    agricultural: AgriculturalIncomeInput = Field(
        default_factory=AgriculturalIncomeInput
    )
    investment: dict[str, float] = Field(default_factory=dict)
    other: OtherIncomeInput = Field(default_factory=OtherIncomeInput)
    obligations: ObligationsInput = Field(default_factory=ObligationsInput)
    deductions: DeductionsInput = Field(default_factory=DeductionsInput)
    toggles: dict[str, bool] = Field(default_factory=dict)
    withholding_tax: float = Field(default=0.0, ge=0)

    @field_validator("locale", mode="before")
    @classmethod
    def _normalise_locale(cls, value: Any) -> str:
        if value is None:
            return "en"
        text = str(value).strip()
        return text or "en"

    @field_validator("investment", mode="before")
    @classmethod
    def _normalise_investment_input(cls, value: Any) -> Mapping[str, Any]:
        if value is None:
            return {}
        if isinstance(value, Mapping):
            return value
        raise TypeError("Investment section must be an object mapping categories to amounts")

    @field_validator("investment", mode="after")
    @classmethod
    def _validate_investment_amounts(cls, value: Mapping[str, Any]) -> dict[str, float]:
        amounts: dict[str, float] = {}
        for key, raw in value.items():
            try:
                amount = float(raw)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Investment amount for category '{key}' must be numeric"
                ) from exc
            if amount < 0:
                raise ValueError(
                    f"Investment amount for category '{key}' cannot be negative"
                )
            amounts[str(key)] = amount
        return amounts

    @field_validator("toggles", mode="before")
    @classmethod
    def _normalise_toggles(cls, value: Any) -> Mapping[str, Any]:
        if value is None:
            return {}
        if isinstance(value, Mapping):
            return value
        raise TypeError(
            "Toggles section must be an object mapping identifiers to booleans"
        )

    @field_validator("toggles", mode="after")
    @classmethod
    def _coerce_toggles(cls, value: Mapping[str, Any]) -> dict[str, bool]:
        toggles: dict[str, bool] = {}
        for key, raw in value.items():
            toggles[str(key)] = bool(raw)
        return toggles


class DeductionBreakdownEntry(BaseModel):
    """Detailed deduction information surfaced in the response."""

    model_config = ConfigDict(extra="forbid")

    type: str
    label: str
    entered: float
    eligible: float
    credit_rate: float
    credit_requested: float
    credit_applied: float
    notes: str | None = None


class SummaryLabels(BaseModel):
    """Localized labels for summary fields."""

    model_config = ConfigDict(extra="forbid")

    income_total: str
    taxable_income: str
    tax_total: str
    net_income: str
    net_monthly_income: str
    average_monthly_tax: str
    effective_tax_rate: str
    deductions_entered: str
    deductions_applied: str
    withholding_tax: str | None = None
    balance_due: str | None = None


class Summary(BaseModel):
    """Aggregated calculation results."""

    model_config = ConfigDict(extra="forbid")

    income_total: float
    taxable_income: float
    tax_total: float
    net_income: float
    net_monthly_income: float
    average_monthly_tax: float
    effective_tax_rate: float
    deductions_entered: float
    deductions_applied: float
    labels: SummaryLabels
    withholding_tax: float | None = None
    balance_due: float | None = None
    balance_due_is_refund: bool | None = None
    deductions_breakdown: list[DeductionBreakdownEntry] | None = None


class DetailEntry(BaseModel):
    """Flexible structure for detailed line items in the response."""

    model_config = ConfigDict(extra="allow")

    category: str
    label: str


class ResponseMeta(BaseModel):
    """Metadata returned alongside the calculation output."""

    model_config = ConfigDict(extra="forbid")

    year: int
    locale: str
    youth_relief_category: str | None = None
    presumptive_adjustments: list[str] | None = None


class CalculationResponse(BaseModel):
    """Full response payload produced by the calculation service."""

    model_config = ConfigDict(extra="forbid")

    summary: Summary
    details: list[DetailEntry]
    meta: ResponseMeta


def format_validation_error(error: ValidationError) -> str:
    """Return a concise human-readable description of validation issues."""

    messages: list[str] = []
    for issue in error.errors():
        location = ".".join(str(part) for part in issue.get("loc", ()))
        message = issue.get("msg", "Invalid value")
        if "greater than or equal to 0" in message.lower():
            message = "value cannot be negative"
        if location:
            messages.append(f"{location}: {message}")
        else:
            messages.append(message)

    details = "; ".join(messages) if messages else str(error)
    return f"Invalid calculation payload: {details}"

