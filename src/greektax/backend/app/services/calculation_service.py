"""Business logic for tax calculations."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Dict, Mapping, Optional, Sequence

from greektax.backend.app.localization import Translator, get_translator
from greektax.backend.config.year_config import (
    EmploymentConfig,
    FreelanceConfig,
    InvestmentConfig,
    PensionConfig,
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
    pension_income: float
    freelance_profit: float
    freelance_contributions: float
    include_trade_fee: bool
    rental_gross_income: float
    rental_deductible_expenses: float
    investment_amounts: Mapping[str, float]

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


def _normalise_payload(payload: Mapping[str, Any]) -> _NormalisedPayload:
    if not isinstance(payload, Mapping):
        raise ValueError("Payload must be a mapping")

    if "year" not in payload:
        raise ValueError("Payload must include a tax year")

    year = _to_int(payload["year"], "year")
    locale = str(payload.get("locale", "en"))

    dependants_section = _extract_section(payload, "dependents")
    children = _to_int(dependants_section.get("children", 0), "dependents.children")

    employment_section = _extract_section(payload, "employment")
    employment_income = _to_float(
        employment_section.get("gross_income", 0.0), "employment.gross_income"
    )

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
    pension_income = _to_float(
        pension_section.get("gross_income", 0.0), "pension.gross_income"
    )

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

    return _NormalisedPayload(
        year=year,
        locale=locale,
        children=children,
        employment_income=employment_income,
        pension_income=pension_income,
        freelance_profit=profit,
        freelance_contributions=contributions,
        include_trade_fee=include_trade_fee,
        rental_gross_income=rental_gross,
        rental_deductible_expenses=rental_expenses,
        investment_amounts=MappingProxyType(investment_amounts),
    )


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


def _calculate_employment(
    payload: _NormalisedPayload,
    config: EmploymentConfig,
    translator: Translator,
) -> Optional[Dict[str, Any]]:
    if not payload.has_employment_income:
        return None

    gross = payload.employment_income
    taxable = gross
    tax_before_credit = _calculate_progressive_tax(taxable, config.brackets)
    credit = config.tax_credit.amount_for_children(payload.children)
    tax_after_credit = tax_before_credit - credit
    if tax_after_credit < 0:
        tax_after_credit = 0.0

    detail = {
        "category": "employment",
        "label": translator("details.employment"),
        "gross_income": _round_currency(gross),
        "taxable_income": _round_currency(taxable),
        "tax_before_credits": _round_currency(tax_before_credit),
        "credits": _round_currency(credit),
        "tax": _round_currency(tax_after_credit),
        "total_tax": _round_currency(tax_after_credit),
        "net_income": _round_currency(gross - tax_after_credit),
    }
    return detail


def _calculate_pension(
    payload: _NormalisedPayload,
    config: PensionConfig,
    translator: Translator,
) -> Optional[Dict[str, Any]]:
    if not payload.has_pension_income:
        return None

    gross = payload.pension_income
    taxable = gross
    tax_before_credit = _calculate_progressive_tax(taxable, config.brackets)
    credit = config.tax_credit.amount_for_children(payload.children)
    tax_after_credit = tax_before_credit - credit
    if tax_after_credit < 0:
        tax_after_credit = 0.0

    return {
        "category": "pension",
        "label": translator("details.pension"),
        "gross_income": _round_currency(gross),
        "taxable_income": _round_currency(taxable),
        "tax_before_credits": _round_currency(tax_before_credit),
        "credits": _round_currency(credit),
        "tax": _round_currency(tax_after_credit),
        "total_tax": _round_currency(tax_after_credit),
        "net_income": _round_currency(gross - tax_after_credit),
    }


def _calculate_trade_fee(payload: _NormalisedPayload, config: FreelanceConfig) -> float:
    if not payload.include_trade_fee:
        return 0.0
    if payload.freelance_taxable_income <= 0:
        return 0.0
    return config.trade_fee.standard_amount


def _calculate_freelance(
    payload: _NormalisedPayload,
    config: FreelanceConfig,
    translator: Translator,
) -> Optional[Dict[str, Any]]:
    if not payload.has_freelance_activity:
        return None

    gross = payload.freelance_profit
    contributions = payload.freelance_contributions
    taxable = payload.freelance_taxable_income
    tax = _calculate_progressive_tax(taxable, config.brackets)
    trade_fee = _calculate_trade_fee(payload, config)
    total_tax = tax + trade_fee
    net_income = gross - contributions - total_tax

    detail = {
        "category": "freelance",
        "label": translator("details.freelance"),
        "gross_income": _round_currency(gross),
        "deductible_contributions": _round_currency(contributions),
        "taxable_income": _round_currency(taxable),
        "tax": _round_currency(tax),
        "trade_fee": _round_currency(trade_fee),
        "total_tax": _round_currency(total_tax),
        "net_income": _round_currency(net_income),
    }
    if trade_fee:
        detail["trade_fee_label"] = translator("details.trade_fee")
    return detail


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


def calculate_tax(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Compute tax summary for the provided payload."""

    normalised = _normalise_payload(payload)
    config: YearConfiguration = load_year_configuration(normalised.year)
    translator = get_translator(normalised.locale)

    details: list[Dict[str, Any]] = []
    employment_detail = _calculate_employment(normalised, config.employment, translator)
    if employment_detail:
        details.append(employment_detail)

    pension_detail = _calculate_pension(normalised, config.pension, translator)
    if pension_detail:
        details.append(pension_detail)

    freelance_detail = _calculate_freelance(normalised, config.freelance, translator)
    if freelance_detail:
        details.append(freelance_detail)

    rental_detail = _calculate_rental(normalised, config.rental, translator)
    if rental_detail:
        details.append(rental_detail)

    investment_detail = _calculate_investment(normalised, config.investment, translator)
    if investment_detail:
        details.append(investment_detail)

    income_total = sum(item.get("gross_income", 0.0) for item in details)
    tax_total = sum(item.get("total_tax", 0.0) for item in details)
    net_income = sum(item.get("net_income", 0.0) for item in details)

    return {
        "summary": {
            "income_total": _round_currency(income_total),
            "tax_total": _round_currency(tax_total),
            "net_income": _round_currency(net_income),
            "labels": {
                "income_total": translator("summary.income_total"),
                "tax_total": translator("summary.tax_total"),
                "net_income": translator("summary.net_income"),
            },
        },
        "details": details,
        "meta": {
            "year": normalised.year,
            "locale": translator.locale,
        },
    }
