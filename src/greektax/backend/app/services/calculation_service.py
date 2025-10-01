"""Business logic for tax calculations."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Dict, Mapping, Optional, Sequence

from greektax.backend.app.localization import Translator, get_translator
from greektax.backend.config.year_config import (
    FreelanceConfig,
    InvestmentConfig,
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
    pension_income: float
    pension_monthly_income: Optional[float]
    pension_payments_per_year: Optional[int]
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

    def total_tax(self) -> float:
        total = self.tax_after_credit
        if self.category == "freelance":
            total += self.trade_fee
        return total

    def net_income(self) -> float:
        net = self.gross_income - self.tax_after_credit
        if self.category == "freelance":
            net -= self.contributions + self.trade_fee
        return net

    def net_income_per_payment(self) -> Optional[float]:
        if not self.payments_per_year or self.payments_per_year <= 0:
            return None
        return self.net_income() / self.payments_per_year


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
    employment_payments: Optional[int] = None
    employment_monthly_income: Optional[float] = None

    if "payments_per_year" in employment_section:
        payments = _to_int(
            employment_section.get("payments_per_year"),
            "employment.payments_per_year",
        )
        if payments <= 0:
            raise ValueError("Field 'employment.payments_per_year' must be positive")
        employment_payments = payments

    if "monthly_income" in employment_section:
        monthly = _to_float(
            employment_section.get("monthly_income", 0.0),
            "employment.monthly_income",
        )
        if monthly > 0:
            employment_monthly_income = monthly

    employment_income = _to_float(
        employment_section.get("gross_income", 0.0), "employment.gross_income"
    )

    if employment_monthly_income is not None:
        payments = employment_payments or 14
        employment_payments = payments
        employment_income = employment_monthly_income * payments
    elif employment_income > 0 and employment_payments:
        employment_monthly_income = employment_income / employment_payments

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
    pension_payments: Optional[int] = None
    pension_monthly_income: Optional[float] = None

    if "payments_per_year" in pension_section:
        payments = _to_int(
            pension_section.get("payments_per_year"), "pension.payments_per_year"
        )
        if payments <= 0:
            raise ValueError("Field 'pension.payments_per_year' must be positive")
        pension_payments = payments

    if "monthly_income" in pension_section:
        monthly = _to_float(
            pension_section.get("monthly_income", 0.0), "pension.monthly_income"
        )
        if monthly > 0:
            pension_monthly_income = monthly

    pension_income = _to_float(
        pension_section.get("gross_income", 0.0), "pension.gross_income"
    )

    if pension_monthly_income is not None:
        payments = pension_payments or 14
        pension_payments = payments
        pension_income = pension_monthly_income * payments
    elif pension_income > 0 and pension_payments:
        pension_monthly_income = pension_income / pension_payments

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

    return _NormalisedPayload(
        year=year,
        locale=locale,
        children=children,
        employment_income=employment_income,
        employment_monthly_income=employment_monthly_income,
        employment_payments_per_year=employment_payments,
        pension_income=pension_income,
        pension_monthly_income=pension_monthly_income,
        pension_payments_per_year=pension_payments,
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


def _calculate_general_income_details(
    payload: _NormalisedPayload,
    config: YearConfiguration,
    translator: Translator,
) -> list[Dict[str, Any]]:
    components: list[_GeneralIncomeComponent] = []

    if payload.has_employment_income:
        components.append(
            _GeneralIncomeComponent(
                category="employment",
                label_key="details.employment",
                gross_income=payload.employment_income,
                taxable_income=payload.employment_income,
                credit_eligible=True,
                payments_per_year=payload.employment_payments_per_year,
                monthly_gross_income=payload.employment_monthly_income,
            )
        )

    if payload.has_pension_income:
        components.append(
            _GeneralIncomeComponent(
                category="pension",
                label_key="details.pension",
                gross_income=payload.pension_income,
                taxable_income=payload.pension_income,
                credit_eligible=True,
                payments_per_year=payload.pension_payments_per_year,
                monthly_gross_income=payload.pension_monthly_income,
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

    if not components:
        return []

    total_taxable = sum(component.taxable_income for component in components)
    brackets = config.employment.brackets
    tax_before_credit = (
        _calculate_progressive_tax(total_taxable, brackets) if total_taxable > 0 else 0.0
    )

    credit_candidates: list[float] = []
    if payload.has_employment_income:
        credit_candidates.append(
            config.employment.tax_credit.amount_for_children(payload.children)
        )
    if payload.has_pension_income:
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
        component.tax_after_credit = max(component.tax_before_credit - component.credit, 0.0)

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

        if component.category == "freelance":
            detail["deductible_contributions"] = _round_currency(component.contributions)
            detail["trade_fee"] = _round_currency(component.trade_fee)
            if component.trade_fee:
                detail["trade_fee_label"] = translator("details.trade_fee")

        if component.monthly_gross_income is not None:
            detail["monthly_gross_income"] = _round_currency(component.monthly_gross_income)

        if component.payments_per_year:
            detail["payments_per_year"] = component.payments_per_year
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

    normalised = _normalise_payload(payload)
    config: YearConfiguration = load_year_configuration(normalised.year)
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
    effective_tax_rate = (tax_total / income_total) if income_total > 0 else 0.0

    return {
        "summary": {
            "income_total": _round_currency(income_total),
            "tax_total": _round_currency(tax_total),
            "net_income": _round_currency(net_income),
            "net_monthly_income": _round_currency(net_monthly_income),
            "effective_tax_rate": _round_rate(effective_tax_rate),
            "labels": {
                "income_total": translator("summary.income_total"),
                "tax_total": translator("summary.tax_total"),
                "net_income": translator("summary.net_income"),
                "net_monthly_income": translator("summary.net_monthly_income"),
                "effective_tax_rate": translator("summary.effective_tax_rate"),
            },
        },
        "details": details,
        "meta": {
            "year": normalised.year,
            "locale": translator.locale,
        },
    }
