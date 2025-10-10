"""Investment income calculator."""

from __future__ import annotations

from typing import Any

from greektax.backend.app.localization import Translator
from greektax.backend.app.models import CalculationInput
from greektax.backend.config.year_config import InvestmentConfig

from .utils import round_currency


def calculate_investment(
    payload: CalculationInput,
    config: InvestmentConfig,
    translator: Translator,
) -> dict[str, Any] | None:
    """Return investment detail row with category breakdown."""

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
                "amount": round_currency(amount),
                "rate": rate,
                "tax": round_currency(tax),
            }
        )

    if gross_total <= 0:
        return None

    net_income = gross_total - tax_total

    return {
        "category": "investment",
        "label": translator("details.investment"),
        "gross_income": round_currency(gross_total),
        "tax": round_currency(tax_total),
        "total_tax": round_currency(tax_total),
        "net_income": round_currency(net_income),
        "items": breakdown,
    }


__all__ = ["calculate_investment"]
