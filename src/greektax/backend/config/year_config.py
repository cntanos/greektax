"""Configuration loader wrapping the shared schema models."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Sequence

import yaml
from pydantic import ValidationError

from .schema import (
    AgriculturalConfig,
    CappedExpenseCreditConfig,
    ConfigurationError,
    ContributionRates,
    DeductionAllowance,
    DeductionConfig,
    DeductionHint,
    DeductionRuleConfig,
    DeductionThreshold,
    DonationCreditConfig,
    EFKACategoryConfig,
    EmploymentConfig,
    EmploymentTaxCredit,
    FamilyTaxCreditMetadata,
    FreelanceConfig,
    HouseholdRateTable,
    InvestmentConfig,
    MedicalCreditConfig,
    MultiRateBracket,
    OtherIncomeConfig,
    PayrollConfig,
    PensionConfig,
    ProgressiveTaxBracket,
    RentalConfig,
    TaxBracket,
    TaxYearManifest,
    TaxYearManifestEntry,
    TradeFeeConfig,
    TradeFeeSunset,
    YearConfiguration,
    YearWarning,
    YouthRateTable,
)

CONFIG_DIRECTORY = Path(__file__).resolve().parent / "data"
MANIFEST_FILE = CONFIG_DIRECTORY / "manifest.yaml"


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ConfigurationError("Configuration file must define a mapping at the top level")
    return data


@lru_cache(maxsize=1)
def load_manifest() -> TaxYearManifest:
    """Load and cache the configuration manifest."""

    if not MANIFEST_FILE.exists():
        raise FileNotFoundError("Configuration manifest not found")

    raw_manifest = _load_yaml(MANIFEST_FILE)

    try:
        return TaxYearManifest.model_validate(raw_manifest)
    except ValidationError as error:  # pragma: no cover - defensive
        raise ConfigurationError(f"Manifest validation failed: {error}") from error


def manifest_entries() -> Sequence[TaxYearManifestEntry]:
    """Expose the configured manifest entries."""

    return load_manifest().years


@lru_cache(maxsize=8)
def load_year_configuration(year: int) -> YearConfiguration:
    """Load configuration for the specified tax year from disk."""

    try:
        manifest_entry = load_manifest().get_entry(year)
    except KeyError as exc:
        raise FileNotFoundError(f"Configuration for year {year} not declared in manifest") from exc

    config_file = CONFIG_DIRECTORY / manifest_entry.resolved_filename
    if not config_file.exists():
        raise FileNotFoundError(
            f"Configuration file for year {year} missing: {config_file.name}"
        )

    raw_config = _load_yaml(config_file)
    raw_config.setdefault("year", year)

    try:
        configuration = YearConfiguration.model_validate(raw_config)
    except ValidationError as error:
        raise ConfigurationError(f"Configuration validation failed for {year}: {error}") from error

    if configuration.year != year:
        raise ConfigurationError(
            f"Configuration year mismatch: expected {year}, found {configuration.year}"
        )

    return configuration


def available_years() -> Sequence[int]:
    """Return the tax years declared in the manifest."""

    return load_manifest().supported_years


__all__ = [
    "AgriculturalConfig",
    "CappedExpenseCreditConfig",
    "CONFIG_DIRECTORY",
    "ConfigurationError",
    "ContributionRates",
    "DeductionAllowance",
    "DeductionConfig",
    "DeductionHint",
    "DeductionRuleConfig",
    "DeductionThreshold",
    "DonationCreditConfig",
    "EFKACategoryConfig",
    "EmploymentConfig",
    "EmploymentTaxCredit",
    "FamilyTaxCreditMetadata",
    "FreelanceConfig",
    "HouseholdRateTable",
    "InvestmentConfig",
    "MANIFEST_FILE",
    "MedicalCreditConfig",
    "MultiRateBracket",
    "OtherIncomeConfig",
    "PayrollConfig",
    "PensionConfig",
    "ProgressiveTaxBracket",
    "RentalConfig",
    "TaxBracket",
    "TaxYearManifest",
    "TaxYearManifestEntry",
    "TradeFeeConfig",
    "TradeFeeSunset",
    "YearConfiguration",
    "YearWarning",
    "YouthRateTable",
    "available_years",
    "load_manifest",
    "load_year_configuration",
    "manifest_entries",
]
