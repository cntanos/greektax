"""Utility helpers for calculator modules."""

from __future__ import annotations

from collections.abc import Sequence

from greektax.backend.config.year_config import TaxBracket


def format_percentage(value: float) -> str:
    """Return a human-readable percentage label for ``value``."""

    percentage = value * 100
    if float(int(percentage)) == percentage:
        return f"{int(percentage)}%"
    return f"{percentage:.2f}%"


def calculate_progressive_tax(amount: float, brackets: Sequence[TaxBracket]) -> float:
    """Calculate progressive tax for ``amount`` using ``brackets``."""

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


def round_currency(value: float) -> float:
    """Round monetary amounts to two decimals."""

    return round(value, 2)


def round_rate(value: float) -> float:
    """Round rate values to four decimals."""

    return round(value, 4)
