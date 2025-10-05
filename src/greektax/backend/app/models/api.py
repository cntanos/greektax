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
)

__all__ = [
    "DependentsInput",
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

    children: int = Field(default=0, ge=0)


class EmploymentInput(BaseModel):
    """Employment income and withholding information."""

    model_config = ConfigDict(extra="forbid")

    gross_income: float = Field(default=0.0, ge=0)
    monthly_income: float | None = Field(default=None, ge=0)
    net_income: float | None = Field(default=None, ge=0)
    net_monthly_income: float | None = Field(default=None, ge=0)
    payments_per_year: int | None = Field(default=None, ge=0)
    employee_contributions: float = Field(default=0.0, ge=0)

    @field_validator("net_income", "net_monthly_income")
    @classmethod
    def _reject_net_income(cls, value: float | None) -> float | None:
        if value is not None and value > 0:
            raise ValueError(NET_INCOME_INPUT_ERROR)
        return value


class PensionInput(BaseModel):
    """Pension income details."""

    model_config = ConfigDict(extra="forbid")

    gross_income: float = Field(default=0.0, ge=0)
    monthly_income: float | None = Field(default=None, ge=0)
    net_income: float | None = Field(default=None, ge=0)
    net_monthly_income: float | None = Field(default=None, ge=0)
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
    trade_fee_location: str = "standard"
    years_active: int | None = Field(default=None, ge=0)
    newly_self_employed: bool = False

    @field_validator("include_trade_fee", "newly_self_employed", mode="before")
    @classmethod
    def _normalise_optional_bool(cls, value: Any, info: ValidationInfo) -> bool:
        if value is None:
            return True if info.field_name == "include_trade_fee" else False
        return value

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
    """Additional annual obligations (ENFIA and luxury tax)."""

    model_config = ConfigDict(extra="forbid")

    enfia: float = Field(default=0.0, ge=0)
    luxury: float = Field(default=0.0, ge=0)


class CalculationRequest(BaseModel):
    """Complete payload accepted by the calculation endpoint."""

    model_config = ConfigDict(extra="forbid")

    year: int = Field(..., ge=0)
    locale: str = Field(default="en")
    dependents: DependentsInput = Field(default_factory=DependentsInput)
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

