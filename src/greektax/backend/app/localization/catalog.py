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
        "details.agricultural": "Agricultural income",
        "details.other": "Other income",
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
        "summary.average_monthly_tax": "Average tax per month",
        "summary.effective_tax_rate": "Effective tax rate",
        "summary.deductions_entered": "Deductions entered",
        "summary.deductions_applied": "Deductions applied",
        "forms.dependents.children": "Dependent children",
        "forms.dependents.children_hint": "Count dependent children who qualify for the AADE family tax credit (typically under 18, full-time students up to 24, or children with a disability). Impacts salary and pension tax credits.",
        "forms.dependents.children_allowance.label": "Family tax credit thresholds",
        "forms.dependents.children_allowance.description": "Automatic tax credits applied to salary and pension income based on dependent children.",
        "forms.dependents.children_allowance.threshold.none": "No dependents",
        "forms.dependents.children_allowance.threshold.one": "1 dependent child",
        "forms.dependents.children_allowance.threshold.two": "2 dependent children",
        "forms.dependents.children_allowance.threshold.three_plus": "3+ dependent children",
        "forms.dependents.children_allowance.threshold.three_plus_note": "Plus €220 for each additional child beyond three.",
        "forms.freelance.mandatory_contributions": "Mandatory social contributions",
        "forms.freelance.mandatory_contributions_hint": "Record mandatory EFKA, health, and auxiliary fund payments backed by receipts; they reduce taxable freelance profits euro-for-euro.",
        "forms.freelance.mandatory_contributions_allowance.label": "Mandatory contribution allowance",
        "forms.freelance.mandatory_contributions_allowance.description": "Mandatory social security payments reduce taxable freelance profits on a euro-for-euro basis.",
        "forms.freelance.mandatory_contributions_allowance.threshold.standard": "Up to 100% of mandatory EFKA and auxiliary contributions",
        "forms.rental.deductible_expenses": "Deductible rental expenses",
        "forms.rental.deductible_expenses_hint": "Maintenance, insurance, and other allowable costs backed by receipts—retain documentation for audits.",
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
        "forms.freelance.efka.category.general_class_1": "General scheme — Class 1",
        "forms.freelance.efka.category.general_class_2": "General scheme — Class 2",
        "forms.freelance.efka.category.general_class_3": "General scheme — Class 3",
        "forms.freelance.efka.category.general_class_4": "General scheme — Class 4",
        "forms.freelance.efka.category.general_class_5": "General scheme — Class 5",
        "forms.freelance.efka.category.general_class_6": "General scheme — Class 6",
        "forms.freelance.efka.category.general_reduced": "General scheme — Reduced contributions",
        "forms.freelance.efka.category.general_reduced_description": "Available to eligible professionals within the reduced-rate window.",
        "forms.freelance.efka.category.engineer_class_1": "Engineers (TSMEDE) — Class 1",
        "forms.freelance.efka.category.engineer_class_2": "Engineers (TSMEDE) — Class 2",
        "forms.freelance.efka.category.engineer_class_3": "Engineers (TSMEDE) — Class 3",
        "forms.freelance.efka.category.engineer_description": "Includes mandatory auxiliary (ΕΤΕΑΕΠ) and lump-sum fund contributions.",
        "forms.deductions.donations": "Charitable donations",
        "forms.deductions.donations_hint": "Documented donations to eligible charities qualify for a 20% tax credit (retain official receipts).",
        "forms.deductions.medical": "Medical expenses",
        "forms.deductions.medical_hint": "Out-of-pocket medical, hospital, and pharmacy costs with receipts; deductible amounts follow AADE limits.",
        "forms.deductions.education": "Education expenses",
        "forms.deductions.education_hint": "Eligible tuition or tutoring expenses for dependents with official receipts; statutory caps apply.",
        "forms.deductions.insurance": "Insurance premiums",
        "forms.deductions.insurance_hint": "Life and health insurance premiums paid to authorised providers with receipts (deduction limits apply).",
    },
    "el": {
        "details.employment": "Εισόδημα μισθωτών",
        "details.freelance": "Εισόδημα ελευθέρων επαγγελματιών",
        "details.trade_fee": "Τέλος επιτηδεύματος",
        "details.pension": "Συντάξεις",
        "details.rental": "Εισόδημα από ενοίκια",
        "details.investment": "Επενδυτικά εισοδήματα",
        "details.agricultural": "Αγροτικό εισόδημα",
        "details.other": "Λοιπά εισοδήματα",
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
        "summary.average_monthly_tax": "Μέσος φόρος ανά μήνα",
        "summary.effective_tax_rate": "Συνολικός φορολογικός συντελεστής",
        "summary.deductions_entered": "Καταχωρημένες εκπτώσεις",
        "summary.deductions_applied": "Εφαρμοσμένες εκπτώσεις",
        "forms.dependents.children": "Εξαρτώμενα τέκνα",
        "forms.dependents.children_hint": "Καταμετρήστε τα εξαρτώμενα τέκνα που δικαιούνται την οικογενειακή έκπτωση ΑΑΔΕ (ανήλικα, φοιτητές έως 24 ή τέκνα με αναπηρία). Επηρεάζει τις εκπτώσεις φόρου μισθών και συντάξεων.",
        "forms.dependents.children_allowance.label": "Κλίμακες οικογενειακής έκπτωσης",
        "forms.dependents.children_allowance.description": "Αυτόματες εκπτώσεις φόρου για μισθωτούς και συνταξιούχους ανάλογα με τα εξαρτώμενα τέκνα.",
        "forms.dependents.children_allowance.threshold.none": "Χωρίς εξαρτώμενα",
        "forms.dependents.children_allowance.threshold.one": "1 εξαρτώμενο τέκνο",
        "forms.dependents.children_allowance.threshold.two": "2 εξαρτώμενα τέκνα",
        "forms.dependents.children_allowance.threshold.three_plus": "3+ εξαρτώμενα τέκνα",
        "forms.dependents.children_allowance.threshold.three_plus_note": "+220 € για κάθε επιπλέον τέκνο πέραν του τρίτου.",
        "forms.freelance.mandatory_contributions": "Υποχρεωτικές εισφορές",
        "forms.freelance.mandatory_contributions_hint": "Καταχωρήστε τις υποχρεωτικές εισφορές ΕΦΚΑ, υγείας και επικουρικών ταμείων με παραστατικά· μειώνουν ισόποσα τα κέρδη του ελευθέρου επαγγέλματος.",
        "forms.freelance.mandatory_contributions_allowance.label": "Όριο υποχρεωτικών εισφορών",
        "forms.freelance.mandatory_contributions_allowance.description": "Οι υποχρεωτικές εισφορές κοινωνικής ασφάλισης μειώνουν ισόποσα τα κέρδη από ελεύθερο επάγγελμα.",
        "forms.freelance.mandatory_contributions_allowance.threshold.standard": "Έως 100% των υποχρεωτικών εισφορών ΕΦΚΑ και επικουρικών",
        "forms.rental.deductible_expenses": "Εκπιπτόμενες δαπάνες ενοικίων",
        "forms.rental.deductible_expenses_hint": "Συντήρηση, ασφάλιστρα και λοιπές επιτρεπόμενες δαπάνες με παραστατικά· διατηρήστε τη σχετική τεκμηρίωση.",
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
        "forms.freelance.efka.category.general_class_1": "Γενικό καθεστώς — Κλάση 1",
        "forms.freelance.efka.category.general_class_2": "Γενικό καθεστώς — Κλάση 2",
        "forms.freelance.efka.category.general_class_3": "Γενικό καθεστώς — Κλάση 3",
        "forms.freelance.efka.category.general_class_4": "Γενικό καθεστώς — Κλάση 4",
        "forms.freelance.efka.category.general_class_5": "Γενικό καθεστώς — Κλάση 5",
        "forms.freelance.efka.category.general_class_6": "Γενικό καθεστώς — Κλάση 6",
        "forms.freelance.efka.category.general_reduced": "Γενικό καθεστώς — Μειωμένες εισφορές",
        "forms.freelance.efka.category.general_reduced_description": "Διαθέσιμη για όσους βρίσκονται εντός του παραθύρου μειωμένου συντελεστή.",
        "forms.freelance.efka.category.engineer_class_1": "Μηχανικοί (ΤΣΜΕΔΕ) — Κλάση 1",
        "forms.freelance.efka.category.engineer_class_2": "Μηχανικοί (ΤΣΜΕΔΕ) — Κλάση 2",
        "forms.freelance.efka.category.engineer_class_3": "Μηχανικοί (ΤΣΜΕΔΕ) — Κλάση 3",
        "forms.freelance.efka.category.engineer_description": "Περιλαμβάνει υποχρεωτικές εισφορές επικουρικού (ΕΤΕΑΕΠ) και εφάπαξ.",
        "forms.deductions.donations": "Δωρεές",
        "forms.deductions.donations_hint": "Τεκμηριωμένες δωρεές σε επιλέξιμους φορείς δικαιούνται έκπτωση φόρου 20% (τηρείτε τα νόμιμα παραστατικά).",
        "forms.deductions.medical": "Ιατρικές δαπάνες",
        "forms.deductions.medical_hint": "Ιατρικές, νοσοκομειακές και φαρμακευτικές δαπάνες με αποδείξεις που εκπίπτουν σύμφωνα με τα όρια της ΑΑΔΕ.",
        "forms.deductions.education": "Εκπαιδευτικές δαπάνες",
        "forms.deductions.education_hint": "Δίδακτρα και φροντιστήρια εξαρτώμενων με νόμιμες αποδείξεις· ισχύουν θεσμοθετημένα όρια.",
        "forms.deductions.insurance": "Ασφαλιστικά ασφάλιστρα",
        "forms.deductions.insurance_hint": "Ασφάλιστρα ζωής και υγείας προς αδειοδοτημένους παρόχους με παραστατικά (εφαρμόζονται περιορισμοί έκπτωσης).",
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
