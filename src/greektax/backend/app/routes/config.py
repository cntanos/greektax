"""Metadata endpoints exposing configuration primitives to the front-end."""

from __future__ import annotations

from typing import Any, Dict

from typing import Any, Dict, List, Sequence

from flask import Blueprint, jsonify, request

from greektax.backend.app.localization import get_translator, normalise_locale
from greektax.backend.config.year_config import (
    ContributionRates,
    EFKACategoryConfig,
    PayrollConfig,
    TradeFeeConfig,
    available_years,
    load_year_configuration,
)

blueprint = Blueprint("config", __name__, url_prefix="/api/v1/config")


def _serialise_payroll_config(config: PayrollConfig) -> Dict[str, Any]:
    return {
        "allowed_payments_per_year": list(config.allowed_payments_per_year),
        "default_payments_per_year": config.default_payments_per_year,
    }


def _serialise_contributions(contributions: ContributionRates) -> Dict[str, Any]:
    return {
        "employee_rate": contributions.employee_rate,
        "employer_rate": contributions.employer_rate,
    }


def _serialise_trade_fee(config: TradeFeeConfig) -> Dict[str, Any]:
    return {
        "standard_amount": config.standard_amount,
        "reduced_amount": config.reduced_amount,
        "newly_self_employed_reduction_years": config.newly_self_employed_reduction_years,
    }


def _serialise_efka_categories(
    categories: Sequence[EFKACategoryConfig],
) -> List[Dict[str, Any]]:
    serialised: List[Dict[str, Any]] = []
    for category in categories:
        serialised.append(
            {
                "id": category.id,
                "label_key": category.label_key,
                "monthly_amount": category.monthly_amount,
                "auxiliary_monthly_amount": category.auxiliary_monthly_amount,
                "description_key": category.description_key,
            }
        )
    return serialised


def _serialise_year(year: int) -> Dict[str, Any]:
    config = load_year_configuration(year)
    return {
        "year": year,
        "meta": dict(config.meta),
        "employment": {
            "payroll": _serialise_payroll_config(config.employment.payroll),
            "contributions": _serialise_contributions(config.employment.contributions),
        },
        "pension": {
            "payroll": _serialise_payroll_config(config.pension.payroll),
            "contributions": _serialise_contributions(config.pension.contributions),
        },
        "freelance": {
            "trade_fee": _serialise_trade_fee(config.freelance.trade_fee),
            "efka_categories": _serialise_efka_categories(
                config.freelance.efka_categories
            ),
        },
    }


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

    hints: list[Dict[str, Any]] = []
    for hint in config.deductions.hints:
        entry: Dict[str, Any] = {
            "id": hint.id,
            "applies_to": list(hint.applies_to),
            "label": translator(hint.label_key),
            "input_id": hint.input_id,
            "validation": dict(hint.validation),
        }
        if hint.description_key:
            entry["description"] = translator(hint.description_key)

        allowances: list[Dict[str, Any]] = []
        for allowance in hint.allowances:
            allowance_entry: Dict[str, Any] = {
                "label": translator(allowance.label_key),
                "thresholds": [],
            }
            if allowance.description_key:
                allowance_entry["description"] = translator(allowance.description_key)

            for threshold in allowance.thresholds:
                threshold_entry: Dict[str, Any] = {
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
