"""Utility helpers for calculator modules."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from greektax.backend.config.year_config import ProgressiveTaxBracket


def format_percentage(value: float) -> str:
    """Return a human-readable percentage label for ``value``."""

    percentage = value * 100
    if float(int(percentage)) == percentage:
        return f"{int(percentage)}%"
    return f"{percentage:.2f}%"


def calculate_progressive_tax(
    amount: float, brackets: Sequence[ProgressiveTaxBracket]
) -> float:
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


def allocate_progressive_tax(
    amounts: Sequence[float],
    brackets: Sequence[ProgressiveTaxBracket],
    rate_resolver: Callable[[int, ProgressiveTaxBracket], float],
) -> list[float]:
    """Distribute progressive tax across ``amounts`` using ``brackets``.

    Parameters
    ----------
    amounts:
        Taxable income per component. Negative values are treated as zero.
    brackets:
        Progressive tax brackets to apply.
    rate_resolver:
        Callable returning the applicable rate for the ``component`` index and
        current ``bracket``. Allows callers to plug in household or youth rate
        tables when ``MultiRateBracket`` instances are supplied.
    """

    if not amounts:
        return []

    remaining = [amount if amount > 0 else 0.0 for amount in amounts]
    taxes = [0.0 for _ in amounts]

    total_remaining = sum(remaining)
    if total_remaining <= 0:
        return taxes

    lower_bound = 0.0

    for bracket in brackets:
        upper = bracket.upper_bound
        if upper is None:
            bracket_capacity = total_remaining
        else:
            bracket_capacity = upper - lower_bound
            if bracket_capacity < 0:
                bracket_capacity = 0.0
            bracket_capacity = min(bracket_capacity, total_remaining)

        if bracket_capacity <= 0:
            lower_bound = upper if upper is not None else lower_bound
            continue

        active_indices = [index for index, value in enumerate(remaining) if value > 0]
        if not active_indices:
            break

        active_total = sum(remaining[index] for index in active_indices)
        if active_total <= 0:
            break

        allocations: dict[int, float] = {}
        allocated = 0.0

        for position, index in enumerate(active_indices):
            remaining_income = remaining[index]
            if remaining_income <= 0:
                continue

            if position == len(active_indices) - 1:
                allocation = min(remaining_income, bracket_capacity - allocated)
            else:
                share = remaining_income / active_total
                allocation = bracket_capacity * share
                allocation = min(allocation, remaining_income)
                remaining_capacity = bracket_capacity - allocated
                allocation = min(allocation, remaining_capacity)

            if allocation < 0:
                allocation = 0.0

            allocations[index] = allocation
            allocated += allocation

        leftover = bracket_capacity - allocated
        if leftover > 1e-9:
            for index in active_indices:
                if leftover <= 1e-9:
                    break
                remaining_income = remaining[index] - allocations.get(index, 0.0)
                if remaining_income <= 0:
                    continue
                extra = remaining_income if remaining_income < leftover else leftover
                if extra <= 0:
                    continue
                allocations[index] = allocations.get(index, 0.0) + extra
                allocated += extra
                leftover -= extra

        for index, allocation in allocations.items():
            if allocation <= 0:
                continue
            rate = rate_resolver(index, bracket)
            taxes[index] += allocation * rate
            remaining[index] -= allocation
            if remaining[index] < 0:
                remaining[index] = 0.0

        total_remaining -= bracket_capacity
        if total_remaining <= 1e-9:
            break
        lower_bound = upper if upper is not None else lower_bound

    return taxes


def round_currency(value: float) -> float:
    """Round monetary amounts to two decimals."""

    return round(value, 2)


def round_rate(value: float) -> float:
    """Round rate values to four decimals."""

    return round(value, 4)
