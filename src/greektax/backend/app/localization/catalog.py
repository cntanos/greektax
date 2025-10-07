"""Translation catalogue helpers backed by shared JSON resources."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cache
from importlib import resources
from typing import Any, Mapping

_BASE_LOCALE = "en"
_TRANSLATIONS_PACKAGE = "greektax.translations"


@dataclass(frozen=True)
class Translator:
    """Callable helper for retrieving localized strings."""

    locale: str
    _messages: Mapping[str, str]
    _fallback: Mapping[str, str]

    def __call__(self, key: str) -> str:
        return self._messages.get(key) or self._fallback.get(key, key)


@dataclass(frozen=True)
class Catalogue:
    """Representation of a locale catalogue backed by the shared resources."""

    locale: str
    backend: Mapping[str, str]
    frontend: Mapping[str, Any]


@cache
def _available_locales() -> tuple[str, ...]:
    """Return the set of locales with published translation payloads."""

    try:
        root = resources.files(_TRANSLATIONS_PACKAGE)
    except ModuleNotFoundError:  # pragma: no cover - defensive fallback
        return (_BASE_LOCALE,)

    locales = sorted(
        entry.stem for entry in root.iterdir() if entry.suffix == ".json"
    )
    return tuple(locales) or (_BASE_LOCALE,)


@cache
def _read_catalogue_payload(locale: str) -> dict[str, Any]:
    """Load the raw translation payload for the requested locale."""

    try:
        resource = resources.files(_TRANSLATIONS_PACKAGE).joinpath(f"{locale}.json")
    except ModuleNotFoundError:  # pragma: no cover - defensive fallback
        return {"backend": {}, "frontend": {}}

    if not resource.is_file():
        return {"backend": {}, "frontend": {}}

    with resource.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    backend = payload.get("backend") or {}
    frontend = payload.get("frontend") or {}
    if not isinstance(backend, dict):  # pragma: no cover - defensive guard
        backend = {}
    if not isinstance(frontend, dict):  # pragma: no cover - defensive guard
        frontend = {}

    return {"backend": backend, "frontend": frontend}


@cache
def _load_catalogue(locale: str) -> Catalogue:
    """Return a cached catalogue representation for the locale."""

    payload = _read_catalogue_payload(locale)
    backend = {key: str(value) for key, value in payload["backend"].items()}
    frontend = payload["frontend"]
    return Catalogue(locale=locale, backend=backend, frontend=frontend)


def normalise_locale(locale: str | None) -> str:
    """Normalise requested locale to a supported catalogue key."""

    if not locale:
        return _BASE_LOCALE

    normalized = locale.lower().split("-")[0]
    return normalized if normalized in _available_locales() else _BASE_LOCALE


def get_translator(locale: str | None = None) -> Translator:
    """Return a translator instance for the requested locale."""

    normalized = normalise_locale(locale)
    catalogue = _load_catalogue(normalized)
    fallback = _load_catalogue(_BASE_LOCALE)
    fallback_messages = fallback.backend if normalized != _BASE_LOCALE else catalogue.backend

    return Translator(
        locale=catalogue.locale,
        _messages=catalogue.backend,
        _fallback=fallback_messages,
    )


def load_translations(locale: str | None = None) -> dict[str, Any]:
    """Expose combined backend/frontend translations for API consumers."""

    normalized = normalise_locale(locale)
    catalogue = _load_catalogue(normalized)
    fallback = _load_catalogue(_BASE_LOCALE)

    return {
        "locale": normalized,
        "available_locales": list(_available_locales()),
        "backend": dict(catalogue.backend),
        "frontend": catalogue.frontend,
        "fallback": {
            "locale": _BASE_LOCALE,
            "backend": dict(fallback.backend),
            "frontend": fallback.frontend,
        },
    }


__all__ = [
    "Translator",
    "Catalogue",
    "get_translator",
    "load_translations",
    "normalise_locale",
]
