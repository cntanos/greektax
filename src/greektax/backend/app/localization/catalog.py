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
        "details.luxury": "Luxury living tax",
        "details.vat": "Value Added Tax",
        "details.enfia": "ENFIA property tax",
        "summary.income_total": "Total income",
        "summary.tax_total": "Total taxes",
        "summary.net_income": "Net income",
        "forms.dependents.children": "Dependent children",
        "forms.dependents.children_hint": "Impacts salary and pension tax credits.",
        "forms.freelance.mandatory_contributions": "Mandatory social contributions",
        "forms.freelance.mandatory_contributions_hint": "Deductible EFKA and auxiliary fund payments.",
        "forms.rental.deductible_expenses": "Deductible rental expenses",
        "forms.rental.deductible_expenses_hint": "Maintenance, insurance, and other allowable costs.",
        "forms.obligations.luxury": "Luxury living tax",
        "forms.obligations.luxury_hint": "Manual input for assets subject to luxury tax.",
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
        "details.luxury": "Φόρος πολυτελούς διαβίωσης",
        "details.vat": "Φόρος Προστιθέμενης Αξίας",
        "details.enfia": "ΕΝΦΙΑ",
        "summary.income_total": "Συνολικό εισόδημα",
        "summary.tax_total": "Συνολικοί φόροι",
        "summary.net_income": "Καθαρό εισόδημα",
        "forms.dependents.children": "Εξαρτώμενα τέκνα",
        "forms.dependents.children_hint": "Επηρεάζει τις εκπτώσεις φόρου μισθών και συντάξεων.",
        "forms.freelance.mandatory_contributions": "Υποχρεωτικές εισφορές",
        "forms.freelance.mandatory_contributions_hint": "Εκπιπτόμενες καταβολές ΕΦΚΑ και επικουρικών ταμείων.",
        "forms.rental.deductible_expenses": "Εκπιπτόμενες δαπάνες ενοικίων",
        "forms.rental.deductible_expenses_hint": "Συντήρηση, ασφάλιστρα και λοιπές επιτρεπόμενες δαπάνες.",
        "forms.obligations.luxury": "Φόρος πολυτελούς διαβίωσης",
        "forms.obligations.luxury_hint": "Χειροκίνητη καταχώρηση για περιουσιακά στοιχεία με φόρο πολυτελείας.",
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
