"""Expose configuration metadata consumed by the decoupled front-end.

These endpoints bridge the YAML-backed year configuration and the SPA so that
UI forms can populate payroll frequencies, trade fee settings, and warning
messages without duplicating business rules.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from flask import Blueprint, jsonify, request

from greektax.backend.app.localization import get_translator, normalise_locale
from greektax.backend.config.year_config import (
    ContributionRates,
    EFKACategoryConfig,
    EmploymentConfig,
    MultiRateBracket,
    PayrollConfig,
    ProgressiveTaxBracket,
    TradeFeeConfig,
    TaxBracket,
    YearWarning,
    available_years,
    load_year_configuration,
)
from greektax.backend.version import get_project_version

blueprint = Blueprint("config", __name__, url_prefix="/api/v1/config")


def _serialise_payroll_config(config: PayrollConfig) -> dict[str, Any]:
    return {
        "allowed_payments_per_year": list(config.allowed_payments_per_year),
        "default_payments_per_year": config.default_payments_per_year,
    }


def _serialise_contributions(contributions: ContributionRates) -> dict[str, Any]:
    return {
        "employee_rate": contributions.employee_rate,
        "employer_rate": contributions.employer_rate,
        "monthly_salary_cap": contributions.monthly_salary_cap,
    }


def _serialise_defaults(meta: Mapping[str, Any], section: str) -> dict[str, bool]:
    defaults_raw = meta.get("defaults")
    if not isinstance(defaults_raw, Mapping):
        return {}

    section_raw = defaults_raw.get(section)
    if not isinstance(section_raw, Mapping):
        return {}

    defaults: dict[str, bool] = {}
    for key, value in section_raw.items():
        defaults[str(key)] = bool(value)
    return defaults


def _serialise_family_tax_credit(config: EmploymentConfig) -> dict[str, Any]:
    return {
        "pending_confirmation": config.family_tax_credit.pending_confirmation,
        "estimate": config.family_tax_credit.estimate,
        "reduction_factor": config.family_tax_credit.reduction_factor,
    }


def _serialise_trade_fee(config: TradeFeeConfig) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "standard_amount": config.standard_amount,
        "reduced_amount": config.reduced_amount,
        "newly_self_employed_reduction_years": config.newly_self_employed_reduction_years,
        "fee_sunset": config.fee_sunset,
    }
    if config.sunset:
        payload["sunset"] = {
            "status_key": config.sunset.status_key,
            "year": config.sunset.year,
            "description_key": config.sunset.description_key,
            "documentation_key": config.sunset.documentation_key,
            "documentation_url": config.sunset.documentation_url,
        }
    return payload


def _serialise_efka_categories(
    categories: Sequence[EFKACategoryConfig],
) -> list[dict[str, Any]]:
    serialised: list[dict[str, Any]] = []
    for category in categories:
        serialised.append(
            {
                "id": category.id,
                "label_key": category.label_key,
                "monthly_amount": category.monthly_amount,
                "auxiliary_monthly_amount": category.auxiliary_monthly_amount,
                "description_key": category.description_key,
                "pension_monthly_amount": category.pension_monthly_amount,
                "health_monthly_amount": category.health_monthly_amount,
                "lump_sum_monthly_amount": category.lump_sum_monthly_amount,
                "estimate": category.estimate,
            }
        )
    return serialised


def _serialise_warning(entry: YearWarning) -> dict[str, Any]:
    return {
        "id": entry.id,
        "message_key": entry.message_key,
        "severity": entry.severity,
        "applies_to": list(entry.applies_to),
        "documentation_key": entry.documentation_key,
        "documentation_url": entry.documentation_url,
    }


def _serialise_multi_rate_bracket(bracket: MultiRateBracket) -> dict[str, Any]:
    household_rates = [
        {"dependants": dependants, "rate": rate}
        for dependants, rate in sorted(bracket.household.dependants.items())
    ]

    youth_rates = [
        {"band": band, "rate": rate}
        for band, rate in sorted(bracket.youth_rates.items())
    ]

    return {
        "type": "multi",
        "upper": bracket.upper_bound,
        "base_rate": bracket.rate,
        "household": {
            "rates": household_rates,
            "reduction_factor": bracket.household.reduction_factor,
        },
        "youth": youth_rates,
        "pending_confirmation": bracket.pending_confirmation,
        "estimate": bracket.estimate,
    }


def _serialise_tax_bracket(bracket: TaxBracket) -> dict[str, Any]:
    return {
        "type": "single",
        "upper": bracket.upper_bound,
        "rate": bracket.rate,
    }


def _serialise_progressive_brackets(
    brackets: Sequence[ProgressiveTaxBracket],
) -> list[dict[str, Any]]:
    serialised: list[dict[str, Any]] = []
    for bracket in brackets:
        if isinstance(bracket, MultiRateBracket):
            serialised.append(_serialise_multi_rate_bracket(bracket))
        else:
            serialised.append(_serialise_tax_bracket(bracket))
    return serialised


def _collect_youth_bands(brackets: Sequence[ProgressiveTaxBracket]) -> list[str]:
    bands: set[str] = set()
    for bracket in brackets:
        if isinstance(bracket, MultiRateBracket):
            bands.update(bracket.youth_rates.keys())
    return sorted(bands)


def _serialise_year(year: int) -> dict[str, Any]:
    config = load_year_configuration(year)
    meta = dict(config.meta)
    toggles_raw = meta.get("toggles") if isinstance(meta, Mapping) else None
    toggles: dict[str, bool] = {}
    if isinstance(toggles_raw, Mapping):
        toggles = {str(key): bool(value) for key, value in toggles_raw.items()}

    employment_brackets = _serialise_progressive_brackets(config.employment.brackets)
    pension_brackets = _serialise_progressive_brackets(config.pension.brackets)
    freelance_brackets = _serialise_progressive_brackets(config.freelance.brackets)
    agricultural_brackets = _serialise_progressive_brackets(
        config.agricultural.brackets
    )
    other_brackets = _serialise_progressive_brackets(config.other.brackets)
    rental_brackets = _serialise_progressive_brackets(config.rental.brackets)

    employment_defaults = _serialise_defaults(meta, "employment")
    freelance_defaults = _serialise_defaults(meta, "freelance")

    return {
        "year": year,
        "meta": meta,
        "toggles": toggles,
        "employment": {
            "payroll": _serialise_payroll_config(config.employment.payroll),
            "contributions": _serialise_contributions(config.employment.contributions),
            "family_tax_credit": _serialise_family_tax_credit(config.employment),
            "tekmiria_reduction_factor": config.employment.tekmiria_reduction_factor,
            "brackets": employment_brackets,
            "defaults": employment_defaults,
            "youth": {
                "bands": _collect_youth_bands(config.employment.brackets),
                "enabled": bool(toggles.get("youth_eligibility")),
            },
            "tekmiria": {
                "enabled": bool(toggles.get("tekmiria_reduction")),
                "reduction_factor": config.employment.tekmiria_reduction_factor,
            },
        },
        "pension": {
            "payroll": _serialise_payroll_config(config.pension.payroll),
            "contributions": _serialise_contributions(config.pension.contributions),
            "brackets": pension_brackets,
            "youth": {
                "bands": _collect_youth_bands(config.pension.brackets),
                "enabled": bool(toggles.get("youth_eligibility")),
            },
        },
        "freelance": {
            "trade_fee": _serialise_trade_fee(config.freelance.trade_fee),
            "efka_categories": _serialise_efka_categories(
                config.freelance.efka_categories
            ),
            "pending_contribution_update": config.freelance.pending_contribution_update,
            "brackets": freelance_brackets,
            "defaults": freelance_defaults,
            "youth": {
                "bands": _collect_youth_bands(config.freelance.brackets),
                "enabled": bool(toggles.get("youth_eligibility")),
            },
        },
        "agricultural": {"brackets": agricultural_brackets},
        "other": {"brackets": other_brackets},
        "rental": {"brackets": rental_brackets},
        "warnings": [_serialise_warning(entry) for entry in config.warnings],
    }


@blueprint.get("/meta")
def get_application_metadata() -> tuple[Any, int]:
    """Expose lightweight application metadata such as the version identifier."""

    payload = {"version": get_project_version()}
    return jsonify(payload), 200


@blueprint.get("/years")
def list_years() -> tuple[Any, int]:
    """Return all configured years with lightweight metadata."""

    years = [_serialise_year(year) for year in available_years()]
    default_year = years[-1]["year"] if years else None
    payload = {"years": years, "default_year": default_year}
    return jsonify(payload), 200


@blueprint.get("/<int:year>/investment-categories")
def get_investment_categories(year: int) -> tuple[Any, int]:
    """Expose configured investment categories with locale-aware labels."""

    try:
        config = load_year_configuration(year)
    except FileNotFoundError as exc:  # pragma: no cover - defensive routing
        return jsonify({"error": "not_found", "message": str(exc)}), 404

    locale_hint = request.args.get("locale")
    locale = normalise_locale(locale_hint)
    translator = get_translator(locale)

    categories = []
    for key, rate in sorted(config.investment.rates.items()):
        categories.append(
            {
                "id": key,
                "label": translator(f"details.investment.{key}"),
                "rate": rate,
            }
        )

    payload = {"year": year, "locale": translator.locale, "categories": categories}
    return jsonify(payload), 200


@blueprint.get("/<int:year>/deductions")
def get_deduction_hints(year: int) -> tuple[Any, int]:
    """Expose deduction hint metadata with locale-aware labelling."""

    try:
        config = load_year_configuration(year)
    except FileNotFoundError as exc:  # pragma: no cover - defensive routing
        return jsonify({"error": "not_found", "message": str(exc)}), 404

    locale_hint = request.args.get("locale")
    locale = normalise_locale(locale_hint)
    translator = get_translator(locale)

    hints: list[dict[str, Any]] = []
    for hint in config.deductions.hints:
        entry: dict[str, Any] = {
            "id": hint.id,
            "applies_to": list(hint.applies_to),
            "label": translator(hint.label_key),
            "input_id": hint.input_id,
            "validation": dict(hint.validation),
        }
        if hint.description_key:
            entry["description"] = translator(hint.description_key)

        allowances: list[dict[str, Any]] = []
        for allowance in hint.allowances:
            allowance_entry: dict[str, Any] = {
                "label": translator(allowance.label_key),
                "thresholds": [],
            }
            if allowance.description_key:
                allowance_entry["description"] = translator(allowance.description_key)

            for threshold in allowance.thresholds:
                threshold_entry: dict[str, Any] = {
                    "label": translator(threshold.label_key),
                }
                if threshold.amount is not None:
                    threshold_entry["amount"] = threshold.amount
                if threshold.percentage is not None:
                    threshold_entry["percentage"] = threshold.percentage
                if threshold.notes_key:
                    threshold_entry["notes"] = translator(threshold.notes_key)
                allowance_entry["thresholds"].append(threshold_entry)

            allowances.append(allowance_entry)

        if allowances:
            entry["allowances"] = allowances
        hints.append(entry)

    payload = {"year": year, "locale": translator.locale, "hints": hints}
    return jsonify(payload), 200
