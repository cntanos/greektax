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
        "summary.net_monthly_income": "Net income per month",
        "summary.effective_tax_rate": "Effective tax rate",
        "forms.dependents.children": "Dependent children",
        "forms.dependents.children_hint": "Impacts salary and pension tax credits.",
        "forms.dependents.children_allowance.label": "Family tax credit thresholds",
        "forms.dependents.children_allowance.description": "Automatic tax credits applied to salary and pension income based on dependent children.",
        "forms.dependents.children_allowance.threshold.none": "No dependents",
        "forms.dependents.children_allowance.threshold.one": "1 dependent child",
        "forms.dependents.children_allowance.threshold.two": "2 dependent children",
        "forms.dependents.children_allowance.threshold.three_plus": "3+ dependent children",
        "forms.dependents.children_allowance.threshold.three_plus_note": "Plus €220 for each additional child beyond three.",
        "forms.freelance.mandatory_contributions": "Mandatory social contributions",
        "forms.freelance.mandatory_contributions_hint": "Deductible EFKA and auxiliary fund payments.",
        "forms.freelance.mandatory_contributions_allowance.label": "Mandatory contribution allowance",
        "forms.freelance.mandatory_contributions_allowance.description": "Mandatory social security payments reduce taxable freelance profits on a euro-for-euro basis.",
        "forms.freelance.mandatory_contributions_allowance.threshold.standard": "Up to 100% of mandatory EFKA and auxiliary contributions",
        "forms.rental.deductible_expenses": "Deductible rental expenses",
        "forms.rental.deductible_expenses_hint": "Maintenance, insurance, and other allowable costs.",
        "forms.rental.deductible_expenses_allowance.label": "Rental expense allowance",
        "forms.rental.deductible_expenses_allowance.description": "Document your eligible maintenance, insurance, and service expenses for deduction.",
        "forms.rental.deductible_expenses_allowance.threshold.documented": "Documented expenses with official receipts",
        "forms.rental.deductible_expenses_allowance.threshold.documented_note": "Retain invoices for repairs, insurance premiums, and common charges to justify deductions.",
        "forms.obligations.luxury": "Luxury living tax",
        "forms.obligations.luxury_hint": "Manual input for assets subject to luxury tax.",
        "forms.obligations.luxury_allowance.label": "Luxury tax reference",
        "forms.obligations.luxury_allowance.description": "Use the assessed amount from the AADE notice for luxury living taxes.",
        "forms.obligations.luxury_allowance.threshold.statement": "AADE assessment statement",
        "forms.obligations.luxury_allowance.threshold.statement_note": "Refer to the official tax statement for the payable amount each year.",
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
        "summary.net_monthly_income": "Καθαρό εισόδημα ανά μήνα",
        "summary.effective_tax_rate": "Συνολικός φορολογικός συντελεστής",
        "forms.dependents.children": "Εξαρτώμενα τέκνα",
        "forms.dependents.children_hint": "Επηρεάζει τις εκπτώσεις φόρου μισθών και συντάξεων.",
        "forms.dependents.children_allowance.label": "Κλίμακες οικογενειακής έκπτωσης",
        "forms.dependents.children_allowance.description": "Αυτόματες εκπτώσεις φόρου για μισθωτούς και συνταξιούχους ανάλογα με τα εξαρτώμενα τέκνα.",
        "forms.dependents.children_allowance.threshold.none": "Χωρίς εξαρτώμενα",
        "forms.dependents.children_allowance.threshold.one": "1 εξαρτώμενο τέκνο",
        "forms.dependents.children_allowance.threshold.two": "2 εξαρτώμενα τέκνα",
        "forms.dependents.children_allowance.threshold.three_plus": "3+ εξαρτώμενα τέκνα",
        "forms.dependents.children_allowance.threshold.three_plus_note": "+220 € για κάθε επιπλέον τέκνο πέραν του τρίτου.",
        "forms.freelance.mandatory_contributions": "Υποχρεωτικές εισφορές",
        "forms.freelance.mandatory_contributions_hint": "Εκπιπτόμενες καταβολές ΕΦΚΑ και επικουρικών ταμείων.",
        "forms.freelance.mandatory_contributions_allowance.label": "Όριο υποχρεωτικών εισφορών",
        "forms.freelance.mandatory_contributions_allowance.description": "Οι υποχρεωτικές εισφορές κοινωνικής ασφάλισης μειώνουν ισόποσα τα κέρδη από ελεύθερο επάγγελμα.",
        "forms.freelance.mandatory_contributions_allowance.threshold.standard": "Έως 100% των υποχρεωτικών εισφορών ΕΦΚΑ και επικουρικών",
        "forms.rental.deductible_expenses": "Εκπιπτόμενες δαπάνες ενοικίων",
        "forms.rental.deductible_expenses_hint": "Συντήρηση, ασφάλιστρα και λοιπές επιτρεπόμενες δαπάνες.",
        "forms.rental.deductible_expenses_allowance.label": "Όριο εκπιπτόμενων δαπανών",
        "forms.rental.deductible_expenses_allowance.description": "Συγκεντρώστε τα παραστατικά συντήρησης, ασφάλισης και κοινόχρηστων για να αιτιολογήσετε τις δαπάνες.",
        "forms.rental.deductible_expenses_allowance.threshold.documented": "Τεκμηριωμένες δαπάνες με νόμιμα παραστατικά",
        "forms.rental.deductible_expenses_allowance.threshold.documented_note": "Διατηρήστε αποδείξεις για επισκευές, ασφάλιστρα και κοινόχρηστα ώστε να εκπίπτουν.",
        "forms.obligations.luxury": "Φόρος πολυτελούς διαβίωσης",
        "forms.obligations.luxury_hint": "Χειροκίνητη καταχώρηση για περιουσιακά στοιχεία με φόρο πολυτελείας.",
        "forms.obligations.luxury_allowance.label": "Αναφορά φόρου πολυτελούς διαβίωσης",
        "forms.obligations.luxury_allowance.description": "Χρησιμοποιήστε το ποσό που αναγράφεται στο εκκαθαριστικό της ΑΑΔΕ.",
        "forms.obligations.luxury_allowance.threshold.statement": "Εκκαθαριστικό ΑΑΔΕ",
        "forms.obligations.luxury_allowance.threshold.statement_note": "Ανατρέξτε στο επίσημο έντυπο για το πληρωτέο ποσό κάθε έτους.",
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
