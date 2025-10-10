"""Expose configuration metadata consumed by the decoupled front-end.

These endpoints bridge the YAML-backed year configuration and the SPA so that
UI forms can populate payroll frequencies, trade fee settings, and warning
messages without duplicating business rules.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields, is_dataclass
from typing import Any, get_args, get_origin, get_type_hints

from flask import Blueprint, jsonify, request

from greektax.backend.app.http import ProblemResponse, problem_response
from greektax.backend.app.localization import (
    Translator,
    get_translator,
    normalise_locale,
)
from greektax.backend.config.year_config import (
    MultiRateBracket,
    ProgressiveTaxBracket,
    TaxBracket,
    TradeFeeConfig,
    available_years,
    load_manifest,
    load_year_configuration,
    YearConfiguration,
)
from greektax.backend.version import get_project_version

blueprint = Blueprint("config", __name__, url_prefix="/api/v1/config")


@dataclass(frozen=True)
class YearRouteContext:
    """Common context shared by year-scoped configuration endpoints."""

    year: int
    locale: str
    translator: Translator
    configuration: YearConfiguration


def _build_year_context(year: int, locale_hint: str | None) -> YearRouteContext | ProblemResponse:
    """Resolve configuration and localisation helpers for a given year."""

    try:
        configuration = load_year_configuration(year)
    except FileNotFoundError as exc:  # pragma: no cover - defensive routing
        return problem_response("not_found", status=404, message=str(exc))

    locale = normalise_locale(locale_hint)
    translator = get_translator(locale)
    return YearRouteContext(
        year=year,
        locale=translator.locale,
        translator=translator,
        configuration=configuration,
    )


def get_configuration_metadata() -> dict[str, Any]:
    """Expose runtime metadata derived from the configuration manifest."""

    manifest = load_manifest()
    supported_years = list(manifest.supported_years)
    default_year = supported_years[-1] if supported_years else None
    return {
        "version": get_project_version(),
        "supported_years": supported_years,
        "default_year": default_year,
    }


def _annotation_contains_dataclass(annotation: Any) -> bool:
    if annotation is None:
        return False

    origin = get_origin(annotation)
    if origin is None:
        return is_dataclass(annotation)

    return any(_annotation_contains_dataclass(arg) for arg in get_args(annotation))


def _serialise_model(value: Any, *, prune_none: bool = False) -> Any:
    """Convert dataclasses or Pydantic models into JSON-ready structures."""

    if value is None:
        return None

    if hasattr(value, "model_dump"):
        data = value.model_dump(mode="python")  # type: ignore[call-arg]
        return _serialise_model(data, prune_none=prune_none)

    if is_dataclass(value):
        hints = get_type_hints(type(value))
        payload: dict[str, Any] = {}
        for field in fields(value):
            field_value = getattr(value, field.name)
            hint = hints.get(field.name)
            if prune_none and field_value is None and _annotation_contains_dataclass(hint):
                continue
            payload[field.name] = _serialise_model(field_value, prune_none=prune_none)
        return payload

    if isinstance(value, Mapping):
        mapping_payload: dict[Any, Any] = {}
        for key, item in value.items():
            serialised = _serialise_model(item, prune_none=prune_none)
            if prune_none and serialised is None:
                continue
            mapping_payload[key] = serialised
        return mapping_payload

    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [
            _serialise_model(item, prune_none=prune_none)
            for item in value
        ]

    return value


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


def _serialise_trade_fee(config: TradeFeeConfig) -> dict[str, Any]:
    payload = _serialise_model(config, prune_none=False)
    if isinstance(payload, Mapping) and payload.get("sunset") is None:
        payload = dict(payload)
        payload.pop("sunset", None)
    return payload


def _serialise_multi_rate_bracket(bracket: MultiRateBracket) -> dict[str, Any]:
    household_rates = [
        {"dependants": dependants, "rate": rate}
        for dependants, rate in sorted(bracket.household.dependants.items())
    ]

    youth_rates = []
    for band, table in sorted(bracket.youth_rates.items()):
        entry: dict[str, Any] = {"band": band}
        if table.rate is not None:
            entry["rate"] = table.rate
        if table.dependants:
            entry["dependant_rates"] = [
                {"dependants": dependants, "rate": rate}
                for dependants, rate in sorted(table.dependants.items())
            ]
        youth_rates.append(entry)

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

    employment_config = config.employment
    pension_config = config.pension
    freelance_config = config.freelance

    return {
        "year": year,
        "meta": meta,
        "toggles": toggles,
        "employment": {
            "payroll": _serialise_model(employment_config.payroll),
            "contributions": _serialise_model(employment_config.contributions),
            "family_tax_credit": _serialise_model(
                employment_config.family_tax_credit
            ),
            "tekmiria_reduction_factor": employment_config.tekmiria_reduction_factor,
            "brackets": employment_brackets,
            "defaults": employment_defaults,
            "youth": {
                "bands": _collect_youth_bands(employment_config.brackets),
            },
            "tekmiria": {
                "enabled": bool(toggles.get("tekmiria_reduction")),
                "reduction_factor": employment_config.tekmiria_reduction_factor,
            },
        },
        "pension": {
            "payroll": _serialise_model(pension_config.payroll),
            "contributions": _serialise_model(pension_config.contributions),
            "brackets": pension_brackets,
            "youth": {
                "bands": _collect_youth_bands(pension_config.brackets),
            },
        },
        "freelance": {
            "trade_fee": _serialise_trade_fee(freelance_config.trade_fee),
            "efka_categories": [
                _serialise_model(category)
                for category in freelance_config.efka_categories
            ],
            "pending_contribution_update": freelance_config.pending_contribution_update,
            "brackets": freelance_brackets,
            "defaults": freelance_defaults,
            "youth": {
                "bands": _collect_youth_bands(freelance_config.brackets),
            },
        },
        "agricultural": {"brackets": agricultural_brackets},
        "other": {"brackets": other_brackets},
        "rental": {"brackets": rental_brackets},
        "warnings": [_serialise_model(entry) for entry in config.warnings],
    }


@blueprint.get("/meta")
def get_application_metadata() -> tuple[Any, int]:
    """Expose lightweight application metadata such as the version identifier."""

    payload = get_configuration_metadata()
    return jsonify(payload), 200


@blueprint.get("/years")
def list_years() -> tuple[Any, int]:
    """Return all configured years with lightweight metadata."""

    years = [_serialise_year(year) for year in available_years()]
    metadata = get_configuration_metadata()
    payload = {
        "years": years,
        "default_year": metadata["default_year"],
        "supported_years": metadata["supported_years"],
    }
    return jsonify(payload), 200


@blueprint.get("/<int:year>/investment-categories")
def get_investment_categories(year: int) -> tuple[Any, int]:
    """Expose configured investment categories with locale-aware labels."""

    locale_hint = request.args.get("locale")
    context = _build_year_context(year, locale_hint)
    if isinstance(context, ProblemResponse):
        return context.to_response()

    categories = []
    for key, rate in sorted(context.configuration.investment.rates.items()):
        categories.append(
            {
                "id": key,
                "label": context.translator(f"details.investment.{key}"),
                "rate": rate,
            }
        )

    payload = {
        "year": context.year,
        "locale": context.locale,
        "categories": categories,
    }
    return jsonify(payload), 200


@blueprint.get("/<int:year>/deductions")
def get_deduction_hints(year: int) -> tuple[Any, int]:
    """Expose deduction hint metadata with locale-aware labelling."""

    locale_hint = request.args.get("locale")
    context = _build_year_context(year, locale_hint)
    if isinstance(context, ProblemResponse):
        return context.to_response()

    hints: list[dict[str, Any]] = []
    for hint in context.configuration.deductions.hints:
        entry: dict[str, Any] = {
            "id": hint.id,
            "applies_to": list(hint.applies_to),
            "label": context.translator(hint.label_key),
            "input_id": hint.input_id,
            "validation": dict(hint.validation),
        }
        if hint.description_key:
            entry["description"] = context.translator(hint.description_key)

        allowances: list[dict[str, Any]] = []
        for allowance in hint.allowances:
            allowance_entry: dict[str, Any] = {
                "label": context.translator(allowance.label_key),
                "thresholds": [],
            }
            if allowance.description_key:
                allowance_entry["description"] = context.translator(
                    allowance.description_key
                )

            for threshold in allowance.thresholds:
                threshold_entry: dict[str, Any] = {
                    "label": context.translator(threshold.label_key),
                }
                if threshold.amount is not None:
                    threshold_entry["amount"] = threshold.amount
                if threshold.percentage is not None:
                    threshold_entry["percentage"] = threshold.percentage
                if threshold.notes_key:
                    threshold_entry["notes"] = context.translator(
                        threshold.notes_key
                    )
                allowance_entry["thresholds"].append(threshold_entry)

            allowances.append(allowance_entry)

        if allowances:
            entry["allowances"] = allowances
        hints.append(entry)

    payload = {"year": context.year, "locale": context.locale, "hints": hints}
    return jsonify(payload), 200
