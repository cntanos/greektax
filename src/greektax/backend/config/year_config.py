"""Year-based configuration loader for Greek tax rules."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import (
    Any,
    Dict,
    Iterable,
    Mapping,
    MutableMapping,
    Optional,
    Sequence,
)

import yaml

CONFIG_DIRECTORY = Path(__file__).resolve().parent / "data"


class ConfigurationError(ValueError):
    """Raised when a configuration file fails validation."""


@dataclass(frozen=True)
class TaxBracket:
    """Represents a single progressive tax bracket."""

    upper_bound: Optional[float]
    rate: float

    def __post_init__(self) -> None:  # pragma: no cover - defensive programming
        if self.rate < 0:
            raise ConfigurationError("Tax rates must be non-negative")
        if self.upper_bound is not None and self.upper_bound <= 0:
            raise ConfigurationError("Upper bounds must be positive values")


@dataclass(frozen=True)
class EmploymentTaxCredit:
    """Year-specific reduction applied to employment income tax."""

    amounts_by_children: Dict[int, float]
    incremental_amount_per_child: float

    def amount_for_children(self, dependants: int) -> float:
        """Return the tax credit amount for the provided dependant count."""

        if dependants < 0:
            return 0.0

        if dependants in self.amounts_by_children:
            return self.amounts_by_children[dependants]

        if not self.amounts_by_children:
            return 0.0

        max_key = max(self.amounts_by_children)
        base_amount = self.amounts_by_children[max_key]
        if dependants <= max_key:
            return base_amount

        extra_children = dependants - max_key
        return base_amount + extra_children * self.incremental_amount_per_child


@dataclass(frozen=True)
class EmploymentConfig:
    """Configuration for salaried/pension income."""

    brackets: Sequence[TaxBracket]
    tax_credit: EmploymentTaxCredit


@dataclass(frozen=True)
class PensionConfig:
    """Configuration for pension income."""

    brackets: Sequence[TaxBracket]
    tax_credit: EmploymentTaxCredit


@dataclass(frozen=True)
class TradeFeeConfig:
    """Settings for the business activity fee (τέλος επιτηδεύματος)."""

    standard_amount: float
    reduced_amount: Optional[float] = None
    newly_self_employed_reduction_years: Optional[int] = None


@dataclass(frozen=True)
class FreelanceConfig:
    """Configuration for freelance/business income."""

    brackets: Sequence[TaxBracket]
    trade_fee: TradeFeeConfig


@dataclass(frozen=True)
class RentalConfig:
    """Configuration for rental income."""

    brackets: Sequence[TaxBracket]


@dataclass(frozen=True)
class InvestmentConfig:
    """Configuration for investment income categories."""

    rates: Dict[str, float]


@dataclass(frozen=True)
class YearConfiguration:
    """Structured representation of a tax year configuration."""

    year: int
    meta: Dict[str, Any]
    employment: EmploymentConfig
    pension: PensionConfig
    freelance: FreelanceConfig
    rental: RentalConfig
    investment: InvestmentConfig


def _parse_tax_brackets(brackets: Iterable[Mapping[str, Any]]) -> Sequence[TaxBracket]:
    parsed: list[TaxBracket] = []
    last_upper: Optional[float] = None

    for bracket in brackets:
        if "rate" not in bracket:
            raise ConfigurationError("Each tax bracket must define a 'rate'")

        rate = float(bracket["rate"])
        upper = bracket.get("upper")
        upper_bound = float(upper) if upper is not None else None

        tax_bracket = TaxBracket(upper_bound=upper_bound, rate=rate)
        if last_upper is not None and tax_bracket.upper_bound is not None:
            if tax_bracket.upper_bound <= last_upper:
                raise ConfigurationError("Tax brackets must be in ascending order")

        parsed.append(tax_bracket)
        last_upper = tax_bracket.upper_bound or last_upper

    if not parsed:
        raise ConfigurationError("At least one tax bracket must be defined")

    if parsed[-1].upper_bound is not None:
        raise ConfigurationError("Final tax bracket must have an open upper bound")

    return parsed


def _parse_tax_credit(raw: Mapping[str, Any]) -> EmploymentTaxCredit:
    amounts_raw = raw.get("amounts_by_children")
    if not isinstance(amounts_raw, MutableMapping):
        raise ConfigurationError("'amounts_by_children' must be a mapping")

    amounts: Dict[int, float] = {}
    for key, value in amounts_raw.items():
        child_count = int(key)
        amounts[child_count] = float(value)

    incremental = float(raw.get("incremental_amount_per_child", 0.0))

    return EmploymentTaxCredit(
        amounts_by_children=amounts,
        incremental_amount_per_child=incremental,
    )


def _parse_employment_config(raw: Mapping[str, Any]) -> EmploymentConfig:
    brackets_raw = raw.get("tax_brackets")
    if not isinstance(brackets_raw, Iterable):
        raise ConfigurationError("Employment configuration must include 'tax_brackets'")

    credit_raw = raw.get("tax_credit")
    if not isinstance(credit_raw, Mapping):
        raise ConfigurationError("Employment configuration must include 'tax_credit'")

    return EmploymentConfig(
        brackets=_parse_tax_brackets(brackets_raw),
        tax_credit=_parse_tax_credit(credit_raw),
    )


def _parse_pension_config(
    raw: Mapping[str, Any], fallback_credit: EmploymentTaxCredit
) -> PensionConfig:
    brackets_raw = raw.get("tax_brackets")
    if not isinstance(brackets_raw, Iterable):
        raise ConfigurationError("Pension configuration must include 'tax_brackets'")

    credit_raw = raw.get("tax_credit")
    if credit_raw is None:
        credit = fallback_credit
    else:
        if not isinstance(credit_raw, Mapping):
            raise ConfigurationError("Pension tax credit must be a mapping")
        credit = _parse_tax_credit(credit_raw)

    return PensionConfig(
        brackets=_parse_tax_brackets(brackets_raw),
        tax_credit=credit,
    )


def _parse_trade_fee(raw: Mapping[str, Any]) -> TradeFeeConfig:
    if "standard_amount" not in raw:
        raise ConfigurationError("Trade fee configuration requires 'standard_amount'")

    standard = float(raw["standard_amount"])
    reduced = raw.get("reduced_amount")
    reduction_years = raw.get("newly_self_employed_reduction_years")

    return TradeFeeConfig(
        standard_amount=standard,
        reduced_amount=float(reduced) if reduced is not None else None,
        newly_self_employed_reduction_years=
        int(reduction_years) if reduction_years is not None else None,
    )


def _parse_freelance_config(raw: Mapping[str, Any]) -> FreelanceConfig:
    brackets_raw = raw.get("tax_brackets")
    if not isinstance(brackets_raw, Iterable):
        raise ConfigurationError("Freelance configuration must include 'tax_brackets'")

    trade_fee_raw = raw.get("trade_fee")
    if not isinstance(trade_fee_raw, Mapping):
        raise ConfigurationError("Freelance configuration must include 'trade_fee'")

    return FreelanceConfig(
        brackets=_parse_tax_brackets(brackets_raw),
        trade_fee=_parse_trade_fee(trade_fee_raw),
    )


def _parse_rental_config(raw: Mapping[str, Any]) -> RentalConfig:
    brackets_raw = raw.get("tax_brackets")
    if not isinstance(brackets_raw, Iterable):
        raise ConfigurationError("Rental configuration must include 'tax_brackets'")

    return RentalConfig(brackets=_parse_tax_brackets(brackets_raw))


def _parse_investment_config(raw: Mapping[str, Any]) -> InvestmentConfig:
    rates_raw = raw.get("rates")
    if not isinstance(rates_raw, MutableMapping):
        raise ConfigurationError("Investment configuration must include a 'rates' mapping")

    rates: Dict[str, float] = {}
    for key, value in rates_raw.items():
        rates[str(key)] = float(value)

    if not rates:
        raise ConfigurationError("Investment configuration requires at least one rate")

    return InvestmentConfig(rates=rates)


def _parse_year_configuration(year: int, raw: Mapping[str, Any]) -> YearConfiguration:
    income_section = raw.get("income")
    if not isinstance(income_section, Mapping):
        raise ConfigurationError("Configuration must include an 'income' section")

    employment_raw = income_section.get("employment")
    if not isinstance(employment_raw, Mapping):
        raise ConfigurationError("Income configuration requires an 'employment' section")

    pension_raw = income_section.get("pension")
    if not isinstance(pension_raw, Mapping):
        raise ConfigurationError("Income configuration requires a 'pension' section")

    freelance_raw = income_section.get("freelance")
    if not isinstance(freelance_raw, Mapping):
        raise ConfigurationError("Income configuration requires a 'freelance' section")

    rental_raw = income_section.get("rental")
    if not isinstance(rental_raw, Mapping):
        raise ConfigurationError("Income configuration requires a 'rental' section")

    investment_raw = income_section.get("investment")
    if not isinstance(investment_raw, Mapping):
        raise ConfigurationError("Income configuration requires an 'investment' section")

    meta = raw.get("meta")
    if meta is None:
        meta = {}
    elif not isinstance(meta, Mapping):
        raise ConfigurationError("'meta' section must be a mapping if provided")

    config_year = raw.get("year")
    if config_year is not None and int(config_year) != year:
        raise ConfigurationError(
            f"Configuration year mismatch: expected {year}, found {config_year}"
        )

    employment_config = _parse_employment_config(employment_raw)

    return YearConfiguration(
        year=year,
        meta=dict(meta),
        employment=employment_config,
        pension=_parse_pension_config(pension_raw, employment_config.tax_credit),
        freelance=_parse_freelance_config(freelance_raw),
        rental=_parse_rental_config(rental_raw),
        investment=_parse_investment_config(investment_raw),
    )


@lru_cache(maxsize=8)
def load_year_configuration(year: int) -> YearConfiguration:
    """Load configuration for the specified tax year from disk."""

    config_file = CONFIG_DIRECTORY / f"{year}.yaml"
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration for year {year} not found")

    with config_file.open("r", encoding="utf-8") as handle:
        raw_config = yaml.safe_load(handle) or {}

    if not isinstance(raw_config, Mapping):
        raise ConfigurationError("Configuration file must define a mapping at the top level")

    return _parse_year_configuration(year, raw_config)


def available_years() -> Sequence[int]:
    """Return a sorted collection of tax years with configuration files."""

    years: set[int] = set()
    for path in CONFIG_DIRECTORY.glob("*.yaml"):
        try:
            years.add(int(path.stem))
        except ValueError:  # pragma: no cover - non-numeric filenames are ignored defensively
            continue

    return tuple(sorted(years))
