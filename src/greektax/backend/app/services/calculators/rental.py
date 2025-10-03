"""Rental income calculator."""

from __future__ import annotations

from typing import Any

from greektax.backend.app.localization import Translator
from greektax.backend.app.models import CalculationInput
from greektax.backend.config.year_config import RentalConfig

from .utils import calculate_progressive_tax, round_currency


def calculate_rental(
    payload: CalculationInput,
    config: RentalConfig,
    translator: Translator,
) -> dict[str, Any] | None:
    """Return rental detail row when rental income is present."""

    if not payload.has_rental_income:
        return None

    gross = payload.rental_gross_income
    expenses = payload.rental_deductible_expenses
    taxable = payload.rental_taxable_income
    tax = calculate_progressive_tax(taxable, config.brackets)
    net_income = gross - expenses - tax

    return {
        "category": "rental",
        "label": translator("details.rental"),
        "gross_income": round_currency(gross),
        "deductible_expenses": round_currency(expenses),
        "taxable_income": round_currency(taxable),
        "tax": round_currency(tax),
        "total_tax": round_currency(tax),
        "net_income": round_currency(net_income),
    }


__all__ = ["calculate_rental"]
