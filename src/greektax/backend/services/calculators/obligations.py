"""Obligation calculators for ENFIA and luxury taxes."""

from __future__ import annotations

from typing import Any

from greektax.backend.app.localization import Translator
from greektax.backend.app.models import CalculationInput

from .utils import round_currency


def calculate_enfia(payload: CalculationInput, translator: Translator) -> dict[str, Any] | None:
    """Return ENFIA detail when the payload declares ENFIA obligations."""

    if not payload.has_enfia_obligation:
        return None

    amount = payload.enfia_due
    rounded = round_currency(amount)
    return {
        "category": "enfia",
        "label": translator("details.enfia"),
        "tax": rounded,
        "total_tax": rounded,
        "net_income": round_currency(-amount),
    }


def calculate_luxury(payload: CalculationInput, translator: Translator) -> dict[str, Any] | None:
    """Return luxury tax detail when the payload declares a luxury obligation."""

    if not payload.has_luxury_obligation:
        return None

    amount = payload.luxury_due
    rounded = round_currency(amount)
    return {
        "category": "luxury",
        "label": translator("details.luxury"),
        "tax": rounded,
        "total_tax": rounded,
        "net_income": round_currency(-amount),
    }
__all__ = ["calculate_enfia", "calculate_luxury"]
