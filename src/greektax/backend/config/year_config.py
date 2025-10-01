"""Year-based configuration loader for Greek tax rules."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import yaml

CONFIG_DIRECTORY = Path(__file__).resolve().parent / "data"


@dataclass
class YearConfiguration:
    """Structured representation of a tax year configuration."""

    year: int
    metadata: Dict[str, Any]

    # TODO: Expand with strongly typed attributes (e.g., brackets, deductions,
    # localized strings) for easier IDE discoverability.


def load_year_configuration(year: int) -> YearConfiguration:
    """Load configuration for the specified tax year from disk.

    TODO: Implement caching and validation of configuration schemas.
    """
    config_file = CONFIG_DIRECTORY / f"{year}.yaml"
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration for year {year} not found")

    # TODO: Validate against schema before constructing the dataclass.
    with config_file.open("r", encoding="utf-8") as handle:
        raw_config = yaml.safe_load(handle)

    return YearConfiguration(year=year, metadata=raw_config)
