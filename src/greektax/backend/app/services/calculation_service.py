"""Business logic for tax calculations."""

from __future__ import annotations

from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence

from greektax.backend.app.localization import Translator, get_translator
from greektax.backend.config.year_config import (
    ContributionRates,
    FreelanceConfig,
    InvestmentConfig,
    PayrollConfig,
    RentalConfig,
    TaxBracket,
    YearConfiguration,
    load_year_configuration,
)


@dataclass(frozen=True)
class _NormalisedPayload:
    """Validates and stores user input in a predictable structure."""

    year: int
    locale: str
    children: int
    employment_income: float
    employment_monthly_income: Optional[float]
    employment_payments_per_year: Optional[int]
    employment_net_target_income: Optional[float]
    pension_income: float
    pension_monthly_income: Optional[float]
    pension_payments_per_year: Optional[int]
    pension_net_target_income: Optional[float]
    freelance_profit: float
    freelance_contributions: float
    include_trade_fee: bool
    rental_gross_income: float
    rental_deductible_expenses: float
    investment_amounts: Mapping[str, float]
    vat_due: float
    enfia_due: float
    luxury_due: float

    @property
    def freelance_taxable_income(self) -> float:
        taxable = self.freelance_profit - self.freelance_contributions
        return taxable if taxable > 0 else 0.0

    @property
    def has_employment_income(self) -> bool:
        return self.employment_income > 0

    @property
    def has_pension_income(self) -> bool:
        return self.pension_income > 0

    @property
    def has_freelance_activity(self) -> bool:
        return (
            self.freelance_profit > 0
            or self.freelance_contributions > 0
            or self.freelance_taxable_income > 0
        )

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
    def has_vat_obligation(self) -> bool:
        return self.vat_due > 0

    @property
    def has_enfia_obligation(self) -> bool:
        return self.enfia_due > 0

    @property
    def has_luxury_obligation(self) -> bool:
        return self.luxury_due > 0


@dataclass
class _GeneralIncomeComponent:
    """Represents an income category that shares the progressive scale."""

    category: str
    label_key: str
    gross_income: float
    taxable_income: float
    credit_eligible: bool
    contributions: float = 0.0
    trade_fee: float = 0.0
    tax_before_credit: float = 0.0
    credit: float = 0.0
    tax_after_credit: float = 0.0
    payments_per_year: Optional[int] = None
    monthly_gross_income: Optional[float] = None
    employee_contributions: float = 0.0
    employer_contributions: float = 0.0

    def total_tax(self) -> float:
        total = self.tax_after_credit
        if self.category == "freelance":
            total += self.trade_fee
        return total

    def net_income(self) -> float:
        net = self.gross_income - self.tax_after_credit
        if self.category == "freelance":
            net -= self.contributions + self.trade_fee
        if self.category in {"employment", "pension"}:
            net -= self.employee_contributions
        return net

    def net_income_per_payment(self) -> Optional[float]:
        if not self.payments_per_year or self.payments_per_year <= 0:
            return None
        return self.net_income() / self.payments_per_year

    def gross_income_per_payment(self) -> Optional[float]:
        if not self.payments_per_year or self.payments_per_year <= 0:
            return None
        return self.gross_income / self.payments_per_year


def _to_float(value: Any, field_name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Field '{field_name}' must be numeric") from exc

    if number < 0:
        raise ValueError(f"Field '{field_name}' cannot be negative")

    return number


def _to_int(value: Any, field_name: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Field '{field_name}' must be an integer") from exc

    if number < 0:
        raise ValueError(f"Field '{field_name}' cannot be negative")

    return number


def _to_bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalised = value.strip().lower()
        if normalised in {"true", "1", "yes", "y"}:
            return True
        if normalised in {"false", "0", "no", "n"}:
            return False

    raise ValueError("Boolean fields accept true/false values only")


def _extract_section(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    section = payload.get(key, {})
    if section is None:
        return {}
    if not isinstance(section, Mapping):
        raise ValueError(f"Section '{key}' must be a mapping")
    return section


def _validate_payments(
    value: Any, payroll: PayrollConfig, field_name: str
) -> Optional[int]:
    if value is None:
        return None

    payments = _to_int(value, field_name)
    if payments not in payroll.allowed_payments_per_year:
        allowed = ", ".join(str(entry) for entry in payroll.allowed_payments_per_year)
        raise ValueError(
            f"Field '{field_name}' must match an allowed payroll frequency ({allowed})"
        )
    return payments


def _normalise_payload(
    payload: Mapping[str, Any], year: int, config: YearConfiguration
) -> _NormalisedPayload:
    if not isinstance(payload, Mapping):
        raise ValueError("Payload must be a mapping")

    locale = str(payload.get("locale", "en"))

    dependants_section = _extract_section(payload, "dependents")
    children = _to_int(dependants_section.get("children", 0), "dependents.children")

    employment_section = _extract_section(payload, "employment")
    employment_payroll = config.employment.payroll
    employment_payments = _validate_payments(
        employment_section.get("payments_per_year"),
        employment_payroll,
        "employment.payments_per_year",
    )

    employment_monthly_income: Optional[float] = None
    employment_income = 0.0
    employment_net_target: Optional[float] = None

    monthly_input = employment_section.get("monthly_income")
    if monthly_input is not None:
        monthly = _to_float(monthly_input, "employment.monthly_income")
        if monthly > 0:
            employment_monthly_income = monthly

    gross_income = _to_float(
        employment_section.get("gross_income", 0.0), "employment.gross_income"
    )

    net_income_value = employment_section.get("net_income")
    if net_income_value is not None:
        net_income = _to_float(net_income_value, "employment.net_income")
        if net_income > 0:
            employment_net_target = net_income

    net_monthly_value = employment_section.get("net_monthly_income")
    if net_monthly_value is not None:
        net_monthly = _to_float(
            net_monthly_value, "employment.net_monthly_income"
        )
        if net_monthly > 0:
            payments = employment_payments or employment_payroll.default_payments_per_year
            employment_payments = payments
            employment_net_target = net_monthly * payments

    if employment_monthly_income is not None:
        payments = employment_payments or employment_payroll.default_payments_per_year
        employment_payments = payments
        employment_income = employment_monthly_income * payments

    if gross_income > 0:
        employment_income = gross_income
        if employment_payments and employment_monthly_income is None:
            employment_monthly_income = employment_income / employment_payments

    if employment_net_target is not None:
        if employment_income > 0 or (employment_monthly_income and employment_monthly_income > 0):
            raise ValueError(
                "Provide either gross or net employment income, not both"
            )
        if employment_payments is None:
            employment_payments = employment_payroll.default_payments_per_year
        employment_monthly_income = None
        employment_income = 0.0

    freelance_section = _extract_section(payload, "freelance")
    profit_value: Optional[Any] = freelance_section.get("profit")
    if profit_value is None:
        revenue = _to_float(
            freelance_section.get("gross_revenue", 0.0), "freelance.gross_revenue"
        )
        expenses = _to_float(
            freelance_section.get("deductible_expenses", 0.0),
            "freelance.deductible_expenses",
        )
        profit = revenue - expenses
        profit = profit if profit > 0 else 0.0
    else:
        profit = _to_float(profit_value, "freelance.profit")

    contributions = _to_float(
        freelance_section.get("mandatory_contributions", 0.0),
        "freelance.mandatory_contributions",
    )

    include_trade_fee = _to_bool(freelance_section.get("include_trade_fee"), True)

    pension_section = _extract_section(payload, "pension")
    pension_payroll = config.pension.payroll
    pension_payments = _validate_payments(
        pension_section.get("payments_per_year"),
        pension_payroll,
        "pension.payments_per_year",
    )

    pension_monthly_income: Optional[float] = None
    pension_income = 0.0
    pension_net_target: Optional[float] = None

    pension_monthly_input = pension_section.get("monthly_income")
    if pension_monthly_input is not None:
        monthly = _to_float(pension_monthly_input, "pension.monthly_income")
        if monthly > 0:
            pension_monthly_income = monthly

    pension_gross = _to_float(
        pension_section.get("gross_income", 0.0), "pension.gross_income"
    )

    pension_net_input = pension_section.get("net_income")
    if pension_net_input is not None:
        net_income = _to_float(pension_net_input, "pension.net_income")
        if net_income > 0:
            pension_net_target = net_income

    pension_net_monthly_input = pension_section.get("net_monthly_income")
    if pension_net_monthly_input is not None:
        net_monthly = _to_float(
            pension_net_monthly_input, "pension.net_monthly_income"
        )
        if net_monthly > 0:
            payments = pension_payments or pension_payroll.default_payments_per_year
            pension_payments = payments
            pension_net_target = net_monthly * payments

    if pension_monthly_income is not None:
        payments = pension_payments or pension_payroll.default_payments_per_year
        pension_payments = payments
        pension_income = pension_monthly_income * payments

    if pension_gross > 0:
        pension_income = pension_gross
        if pension_payments and pension_monthly_income is None:
            pension_monthly_income = pension_income / pension_payments

    if pension_net_target is not None:
        if pension_income > 0 or (pension_monthly_income and pension_monthly_income > 0):
            raise ValueError("Provide either gross or net pension income, not both")
        if pension_payments is None:
            pension_payments = pension_payroll.default_payments_per_year
        pension_monthly_income = None
        pension_income = 0.0

    rental_section = _extract_section(payload, "rental")
    rental_gross = _to_float(
        rental_section.get("gross_income", 0.0), "rental.gross_income"
    )
    rental_expenses = _to_float(
        rental_section.get("deductible_expenses", 0.0),
        "rental.deductible_expenses",
    )

    investment_section = _extract_section(payload, "investment")
    investment_amounts: Dict[str, float] = {}
    for key, value in investment_section.items():
        investment_amounts[str(key)] = _to_float(value, f"investment.{key}")

    obligations_section = _extract_section(payload, "obligations")
    vat_due = _to_float(obligations_section.get("vat", 0.0), "obligations.vat")
    enfia_due = _to_float(obligations_section.get("enfia", 0.0), "obligations.enfia")
    luxury_due = _to_float(
        obligations_section.get("luxury", 0.0), "obligations.luxury"
    )

    normalised = _NormalisedPayload(
        year=year,
        locale=locale,
        children=children,
        employment_income=employment_income,
        employment_monthly_income=employment_monthly_income,
        employment_payments_per_year=employment_payments,
        employment_net_target_income=employment_net_target,
        pension_income=pension_income,
        pension_monthly_income=pension_monthly_income,
        pension_payments_per_year=pension_payments,
        pension_net_target_income=pension_net_target,
        freelance_profit=profit,
        freelance_contributions=contributions,
        include_trade_fee=include_trade_fee,
        rental_gross_income=rental_gross,
        rental_deductible_expenses=rental_expenses,
        investment_amounts=MappingProxyType(investment_amounts),
        vat_due=vat_due,
        enfia_due=enfia_due,
        luxury_due=luxury_due,
    )

    return _apply_net_targets(normalised, config)


def _apply_net_targets(
    payload: _NormalisedPayload, config: YearConfiguration
) -> _NormalisedPayload:
    adjusted = payload

    if payload.employment_net_target_income:
        adjusted = _solve_net_target(
            adjusted,
            config,
            category="employment",
            target=payload.employment_net_target_income,
        )

    if adjusted.pension_net_target_income:
        adjusted = _solve_net_target(
            adjusted,
            config,
            category="pension",
            target=adjusted.pension_net_target_income,
        )

    return adjusted


def _set_component_income(
    payload: _NormalisedPayload, category: str, gross_income: float, payments: int
) -> _NormalisedPayload:
    monthly_income = gross_income / payments if payments > 0 else None
    if category == "employment":
        return replace(
            payload,
            employment_income=gross_income,
            employment_monthly_income=monthly_income,
            employment_payments_per_year=payments,
        )

    if category == "pension":
        return replace(
            payload,
            pension_income=gross_income,
            pension_monthly_income=monthly_income,
            pension_payments_per_year=payments,
        )

    raise ValueError(f"Unsupported category for net target resolution: {category}")


def _solve_net_target(
    payload: _NormalisedPayload,
    config: YearConfiguration,
    *,
    category: str,
    target: float,
) -> _NormalisedPayload:
    if target <= 0:
        if category == "employment":
            return replace(
                payload,
                employment_income=0.0,
                employment_monthly_income=None,
                employment_net_target_income=None,
            )
        return replace(
            payload,
            pension_income=0.0,
            pension_monthly_income=None,
            pension_net_target_income=None,
        )

    if category == "employment":
        payments = payload.employment_payments_per_year or config.employment.payroll.default_payments_per_year
        contribution_rate = config.employment.contributions.employee_rate
    else:
        payments = payload.pension_payments_per_year or config.pension.payroll.default_payments_per_year
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

    if category == "employment":
        return replace(best_payload, employment_net_target_income=None)

    return replace(best_payload, pension_net_target_income=None)


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


def _calculate_trade_fee(payload: _NormalisedPayload, config: FreelanceConfig) -> float:
    if not payload.include_trade_fee:
        return 0.0
    if payload.freelance_taxable_income <= 0:
        return 0.0
    return config.trade_fee.standard_amount


def _build_general_income_components(
    payload: _NormalisedPayload, config: YearConfiguration
) -> list[_GeneralIncomeComponent]:
    components: list[_GeneralIncomeComponent] = []

    if payload.has_employment_income:
        employee_contrib = (
            payload.employment_income * config.employment.contributions.employee_rate
        )
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
            _GeneralIncomeComponent(
                category="employment",
                label_key="details.employment",
                gross_income=payload.employment_income,
                taxable_income=payload.employment_income,
                credit_eligible=True,
                payments_per_year=payload.employment_payments_per_year,
                monthly_gross_income=monthly_income,
                employee_contributions=employee_contrib,
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
            _GeneralIncomeComponent(
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
            _GeneralIncomeComponent(
                category="freelance",
                label_key="details.freelance",
                gross_income=payload.freelance_profit,
                taxable_income=payload.freelance_taxable_income,
                credit_eligible=False,
                contributions=payload.freelance_contributions,
                trade_fee=trade_fee,
            )
        )

    return components


def _apply_progressive_tax(
    components: Sequence[_GeneralIncomeComponent],
    payload: _NormalisedPayload,
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


def _calculate_general_income_details(
    payload: _NormalisedPayload,
    config: YearConfiguration,
    translator: Translator,
) -> list[Dict[str, Any]]:
    components = _build_general_income_components(payload, config)
    if not components:
        return []

    _apply_progressive_tax(components, payload, config)

    details: list[Dict[str, Any]] = []
    for component in components:
        detail: Dict[str, Any] = {
            "category": component.category,
            "label": translator(component.label_key),
            "gross_income": _round_currency(component.gross_income),
            "taxable_income": _round_currency(component.taxable_income),
            "tax": _round_currency(component.tax_after_credit),
            "total_tax": _round_currency(component.total_tax()),
            "net_income": _round_currency(component.net_income()),
        }

        if component.category in {"employment", "pension"}:
            detail["tax_before_credits"] = _round_currency(component.tax_before_credit)
            detail["credits"] = _round_currency(component.credit)
            if component.employee_contributions:
                detail["employee_contributions"] = _round_currency(
                    component.employee_contributions
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

        if component.category == "freelance":
            detail["deductible_contributions"] = _round_currency(component.contributions)
            detail["trade_fee"] = _round_currency(component.trade_fee)
            if component.trade_fee:
                detail["trade_fee_label"] = translator("details.trade_fee")

        if component.monthly_gross_income is not None:
            detail["monthly_gross_income"] = _round_currency(component.monthly_gross_income)

        if component.payments_per_year:
            detail["payments_per_year"] = component.payments_per_year
            gross_per_payment = component.gross_income_per_payment()
            if gross_per_payment is not None:
                detail["gross_income_per_payment"] = _round_currency(gross_per_payment)
            net_per_payment = component.net_income_per_payment()
            if net_per_payment is not None:
                detail["net_income_per_payment"] = _round_currency(net_per_payment)

        details.append(detail)

    return details


def _calculate_rental(
    payload: _NormalisedPayload,
    config: RentalConfig,
    translator: Translator,
) -> Optional[Dict[str, Any]]:
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
    payload: _NormalisedPayload,
    config: InvestmentConfig,
    translator: Translator,
) -> Optional[Dict[str, Any]]:
    if not payload.has_investment_income:
        return None

    breakdown: list[Dict[str, Any]] = []
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


def _calculate_vat(payload: _NormalisedPayload, translator: Translator) -> Optional[Dict[str, Any]]:
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


def _calculate_enfia(payload: _NormalisedPayload, translator: Translator) -> Optional[Dict[str, Any]]:
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


def _calculate_luxury(payload: _NormalisedPayload, translator: Translator) -> Optional[Dict[str, Any]]:
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


def calculate_tax(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Compute tax summary for the provided payload."""

    if not isinstance(payload, Mapping):
        raise ValueError("Payload must be a mapping")

    if "year" not in payload:
        raise ValueError("Payload must include a tax year")

    year = _to_int(payload["year"], "year")
    config: YearConfiguration = load_year_configuration(year)
    normalised = _normalise_payload(payload, year, config)
    translator = get_translator(normalised.locale)

    details: list[Dict[str, Any]] = []
    general_income_details = _calculate_general_income_details(normalised, config, translator)
    details.extend(general_income_details)

    rental_detail = _calculate_rental(normalised, config.rental, translator)
    if rental_detail:
        details.append(rental_detail)

    investment_detail = _calculate_investment(normalised, config.investment, translator)
    if investment_detail:
        details.append(investment_detail)

    vat_detail = _calculate_vat(normalised, translator)
    if vat_detail:
        details.append(vat_detail)

    enfia_detail = _calculate_enfia(normalised, translator)
    if enfia_detail:
        details.append(enfia_detail)

    luxury_detail = _calculate_luxury(normalised, translator)
    if luxury_detail:
        details.append(luxury_detail)

    income_total = sum(item.get("gross_income", 0.0) for item in details)
    tax_total = sum(item.get("total_tax", 0.0) for item in details)
    net_income = sum(item.get("net_income", 0.0) for item in details)
    net_monthly_income = net_income / 12 if net_income else 0.0
    average_monthly_tax = tax_total / 12 if tax_total else 0.0
    effective_tax_rate = (tax_total / income_total) if income_total > 0 else 0.0

    return {
        "summary": {
            "income_total": _round_currency(income_total),
            "tax_total": _round_currency(tax_total),
            "net_income": _round_currency(net_income),
            "net_monthly_income": _round_currency(net_monthly_income),
            "average_monthly_tax": _round_currency(average_monthly_tax),
            "effective_tax_rate": _round_rate(effective_tax_rate),
            "labels": {
                "income_total": translator("summary.income_total"),
                "tax_total": translator("summary.tax_total"),
                "net_income": translator("summary.net_income"),
                "net_monthly_income": translator("summary.net_monthly_income"),
                "average_monthly_tax": translator("summary.average_monthly_tax"),
                "effective_tax_rate": translator("summary.effective_tax_rate"),
            },
        },
        "details": details,
        "meta": {
            "year": normalised.year,
            "locale": translator.locale,
        },
    }
