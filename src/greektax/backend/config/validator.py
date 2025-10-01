"""Utilities for validating year configuration data and surfacing issues."""

from __future__ import annotations

import argparse
from collections import Counter
from typing import Iterable, Mapping, Sequence

from .year_config import (
    ContributionRates,
    DeductionConfig,
    DeductionHint,
    EFKACategoryConfig,
    PayrollConfig,
    TradeFeeConfig,
    YearConfiguration,
    YearWarning,
    available_years,
    load_year_configuration,
)


def _format_scope(scope: str, message: str) -> str:
    return f"{scope}: {message}"


def _validate_payroll(scope: str, payroll: PayrollConfig) -> list[str]:
    errors: list[str] = []
    allowed = list(payroll.allowed_payments_per_year)

    if not allowed:
        errors.append(_format_scope(scope, "no allowed payroll frequencies defined"))
        return errors

    invalid_entries = [value for value in allowed if value <= 0]
    if invalid_entries:
        errors.append(
            _format_scope(
                scope,
                "allowed payroll frequencies must be positive integers",
            )
        )

    duplicates = [value for value, count in Counter(allowed).items() if count > 1]
    if duplicates:
        errors.append(
            _format_scope(
                scope,
                f"duplicate payroll frequency values detected: {sorted(duplicates)}",
            )
        )

    if allowed != sorted(allowed):
        errors.append(
            _format_scope(scope, "allowed payroll frequencies should be sorted"),
        )

    default_frequency = payroll.default_payments_per_year
    if default_frequency not in allowed:
        errors.append(
            _format_scope(
                scope,
                (
                    "default payroll frequency "
                    f"{default_frequency} is not present in the allowed set"
                ),
            )
        )

    return errors


def _validate_contributions(scope: str, contributions: ContributionRates) -> list[str]:
    errors: list[str] = []

    for label, value in {
        "employee": contributions.employee_rate,
        "employer": contributions.employer_rate,
    }.items():
        if value < 0 or value > 1:
            errors.append(
                _format_scope(
                    scope,
                    f"{label} contribution rate {value} must be between 0 and 1",
                )
            )

    return errors


def _validate_trade_fee(trade_fee: TradeFeeConfig) -> list[str]:
    errors: list[str] = []

    if trade_fee.standard_amount < 0:
        errors.append(
            _format_scope("freelance.trade_fee", "standard amount must be non-negative"),
        )

    reduced = trade_fee.reduced_amount
    if reduced is not None:
        if reduced < 0:
            errors.append(
                _format_scope(
                    "freelance.trade_fee",
                    "reduced amount must be non-negative",
                )
            )
        if reduced > trade_fee.standard_amount:
            errors.append(
                _format_scope(
                    "freelance.trade_fee",
                    "reduced amount cannot exceed the standard amount",
                )
            )

    sunset = trade_fee.sunset
    if sunset and sunset.documentation_url:
        if not sunset.documentation_url.startswith(("http://", "https://")):
            errors.append(
                _format_scope(
                    "freelance.trade_fee",
                    "sunset documentation URL must be absolute",
                )
            )

    return errors


def _validate_efka_categories(categories: Sequence[EFKACategoryConfig]) -> list[str]:
    errors: list[str] = []

    seen_ids: set[str] = set()
    for category in categories:
        if category.id in seen_ids:
            errors.append(
                _format_scope(
                    "freelance.efka_categories",
                    f"duplicate category identifier '{category.id}' detected",
                )
            )
        else:
            seen_ids.add(category.id)

        if category.monthly_amount < 0:
            errors.append(
                _format_scope(
                    "freelance.efka_categories",
                    f"category '{category.id}' monthly amount must be non-negative",
                )
            )

        auxiliary_amount = category.auxiliary_monthly_amount
        if auxiliary_amount is not None and auxiliary_amount < 0:
            errors.append(
                _format_scope(
                    "freelance.efka_categories",
                    (
                        "category "
                        f"'{category.id}' auxiliary monthly amount must be non-negative"
                    ),
                )
            )

        pension_amount = category.pension_monthly_amount
        if pension_amount is not None and pension_amount < 0:
            errors.append(
                _format_scope(
                    "freelance.efka_categories",
                    (
                        "category "
                        f"'{category.id}' pension monthly amount must be non-negative"
                    ),
                )
            )

        health_amount = category.health_monthly_amount
        if health_amount is not None and health_amount < 0:
            errors.append(
                _format_scope(
                    "freelance.efka_categories",
                    (
                        "category "
                        f"'{category.id}' health monthly amount must be non-negative"
                    ),
                )
            )

        lump_sum_amount = category.lump_sum_monthly_amount
        if lump_sum_amount is not None and lump_sum_amount < 0:
            errors.append(
                _format_scope(
                    "freelance.efka_categories",
                    (
                        "category "
                        f"'{category.id}' lump-sum monthly amount must be non-negative"
                    ),
                )
            )

    return errors


def _validate_investment_rates(rates: Mapping[str, float]) -> list[str]:
    errors: list[str] = []
    for category, rate in rates.items():
        if rate < 0 or rate > 1:
            errors.append(
                _format_scope(
                    "investment.rates",
                    f"rate for '{category}' must be between 0 and 1",
                )
            )
    return errors


def _validate_deduction_allowances(hint: DeductionHint) -> list[str]:
    errors: list[str] = []
    for allowance in hint.allowances:
        if not allowance.thresholds:
            errors.append(
                _format_scope(
                    f"deductions.{hint.id}",
                    f"allowance '{allowance.label_key}' must define thresholds",
                )
            )
            continue

        for threshold in allowance.thresholds:
            if threshold.amount is not None and threshold.amount < 0:
                errors.append(
                    _format_scope(
                        f"deductions.{hint.id}",
                        (
                            "threshold "
                            f"'{threshold.label_key}' amount must be non-negative"
                        ),
                    )
                )
            if threshold.percentage is not None:
                if threshold.percentage < 0 or threshold.percentage > 1:
                    errors.append(
                        _format_scope(
                            f"deductions.{hint.id}",
                            (
                                "threshold "
                                f"'{threshold.label_key}' percentage must be between 0 and 1"
                            ),
                        )
                    )

    return errors


def _validate_deductions(config: DeductionConfig) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()

    for hint in config.hints:
        if hint.id in seen_ids:
            errors.append(
                _format_scope(
                    "deductions",
                    f"duplicate hint identifier '{hint.id}' detected",
                )
            )
        else:
            seen_ids.add(hint.id)

        if "type" not in hint.validation:
            errors.append(
                _format_scope(
                    f"deductions.{hint.id}",
                    "validation metadata must define a 'type' value",
                )
            )

        errors.extend(_validate_deduction_allowances(hint))

    return errors


def _validate_warnings(warnings: Iterable[YearWarning]) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()
    valid_severities = {"info", "warning", "error"}

    for warning in warnings:
        if warning.id in seen_ids:
            errors.append(
                _format_scope(
                    "warnings",
                    f"duplicate warning identifier '{warning.id}' detected",
                )
            )
        else:
            seen_ids.add(warning.id)

        if warning.severity not in valid_severities:
            errors.append(
                _format_scope(
                    f"warnings.{warning.id}",
                    f"severity '{warning.severity}' is not recognised",
                )
            )

        for target in warning.applies_to:
            if not target.strip():
                errors.append(
                    _format_scope(
                        f"warnings.{warning.id}",
                        "applies_to entries must be non-empty strings",
                    )
                )

        if warning.documentation_url and not warning.documentation_url.startswith(
            ("http://", "https://")
        ):
            errors.append(
                _format_scope(
                    f"warnings.{warning.id}",
                    "documentation URL must be absolute",
                )
            )

    return errors


def validate_year_configuration(config: YearConfiguration) -> list[str]:
    """Return a list of validation issues for the provided configuration."""

    errors: list[str] = []

    errors.extend(_validate_payroll("employment.payroll", config.employment.payroll))
    errors.extend(_validate_payroll("pension.payroll", config.pension.payroll))

    errors.extend(
        _validate_contributions("employment.contributions", config.employment.contributions)
    )
    errors.extend(
        _validate_contributions("pension.contributions", config.pension.contributions)
    )

    errors.extend(_validate_trade_fee(config.freelance.trade_fee))
    errors.extend(_validate_efka_categories(config.freelance.efka_categories))
    errors.extend(_validate_investment_rates(config.investment.rates))
    errors.extend(_validate_deductions(config.deductions))
    errors.extend(_validate_warnings(config.warnings))

    return errors


def validate_all_years(years: Sequence[int] | None = None) -> dict[int, list[str]]:
    """Validate all configured years and return issues keyed by year."""

    targets = years or available_years()
    results: dict[int, list[str]] = {}

    for year in targets:
        config = load_year_configuration(year)
        results[int(year)] = validate_year_configuration(config)

    return results


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate configured tax years and report issues helpful to contributors."
        )
    )
    parser.add_argument(
        "years",
        nargs="*",
        type=int,
        help="Specific years to validate (defaults to all configured years)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for running validations from the command line."""

    parser = _build_argument_parser()
    args = parser.parse_args(argv)
    years = args.years or available_years()

    if not years:
        parser.print_help()
        return 1

    exit_code = 0

    for year in years:
        try:
            config = load_year_configuration(year)
        except FileNotFoundError as error:
            print(f"[{year}] failed to load configuration: {error}")
            exit_code = 1
            continue

        issues = validate_year_configuration(config)
        if issues:
            exit_code = 1
            print(f"[{year}] {len(issues)} issue(s) detected:")
            for issue in issues:
                print(f"  - {issue}")
        else:
            print(f"[{year}] OK")

    return exit_code


if __name__ == "__main__":  # pragma: no cover - CLI invocation
    raise SystemExit(main())
