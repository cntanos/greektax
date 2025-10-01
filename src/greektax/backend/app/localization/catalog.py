"""Lightweight translation catalogue for backend responses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

_BASE_LOCALE = "en"

_MESSAGES: Dict[str, Dict[str, str]] = {
    "en": {
        "details.employment": "Employment income",
        "details.freelance": "Freelance income",
        "details.trade_fee": "Business activity fee",
        "details.pension": "Pension income",
        "details.rental": "Rental income",
        "details.investment": "Investment income",
        "details.investment.dividends": "Dividends",
        "details.investment.interest": "Interest",
        "details.investment.capital_gains": "Capital gains",
        "details.investment.royalties": "Royalties",
        "summary.income_total": "Total income",
        "summary.tax_total": "Total taxes",
        "summary.net_income": "Net income",
    },
    "el": {
        "details.employment": "Εισόδημα μισθωτών",
        "details.freelance": "Εισόδημα ελευθέρων επαγγελματιών",
        "details.trade_fee": "Τέλος επιτηδεύματος",
        "details.pension": "Συντάξεις",
        "details.rental": "Εισόδημα από ενοίκια",
        "details.investment": "Επενδυτικά εισοδήματα",
        "details.investment.dividends": "Μερίσματα",
        "details.investment.interest": "Τόκοι",
        "details.investment.capital_gains": "Κεφαλαιακά κέρδη",
        "details.investment.royalties": "Δικαιώματα",
        "summary.income_total": "Συνολικό εισόδημα",
        "summary.tax_total": "Συνολικοί φόροι",
        "summary.net_income": "Καθαρό εισόδημα",
    },
}


@dataclass(frozen=True)
class Translator:
    """Callable helper for retrieving localized strings."""

    locale: str
    _messages: Dict[str, str]
    _fallback: Dict[str, str]

    def __call__(self, key: str) -> str:
        return self._messages.get(key) or self._fallback.get(key, key)


def normalise_locale(locale: str | None) -> str:
    """Normalise requested locale to a supported catalogue key."""

    if not locale:
        return _BASE_LOCALE

    normalized = locale.lower().split("-")[0]
    return normalized if normalized in _MESSAGES else _BASE_LOCALE


def get_translator(locale: str | None = None) -> Translator:
    """Return a translator instance for the requested locale."""

    normalized = normalise_locale(locale)
    messages = _MESSAGES.get(normalized, {})
    fallback = _MESSAGES[_BASE_LOCALE]
    if normalized == _BASE_LOCALE:
        return Translator(locale=normalized, _messages=messages, _fallback=messages)

    return Translator(locale=normalized, _messages=messages, _fallback=fallback)


__all__ = ["Translator", "get_translator", "normalise_locale"]
