"""Unit coverage for year configuration discovery and parsing utilities."""

from __future__ import annotations

from pathlib import Path
from shutil import copy2

import pytest

from greektax.backend.config import year_config


@pytest.fixture()
def isolated_config_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Return a temporary configuration directory patched into ``year_config``."""

    original_directory = year_config.CONFIG_DIRECTORY
    for filename in ("2024.yaml", "2025.yaml", "2026.yaml"):
        copy2(original_directory / filename, tmp_path / filename)

    monkeypatch.setattr(year_config, "CONFIG_DIRECTORY", tmp_path)
    year_config.load_year_configuration.cache_clear()

    yield tmp_path

    year_config.load_year_configuration.cache_clear()


def test_available_years_discovers_new_config_file(
    isolated_config_directory: Path,
) -> None:
    """The helper should surface any new ``*.yaml`` files without code changes."""

    new_year_path = isolated_config_directory / "2030.yaml"
    new_year_path.write_text((isolated_config_directory / "2026.yaml").read_text())

    years = year_config.available_years()

    assert years == (2024, 2025, 2026, 2030)


def test_available_years_ignores_non_numeric_filenames(
    isolated_config_directory: Path,
) -> None:
    """Non-numeric filenames should be ignored to avoid unexpected crashes."""

    (isolated_config_directory / "legacy.yaml").write_text("meta: {}\n")
    (isolated_config_directory / "2025.backup").write_text("meta: {}\n")
    (isolated_config_directory / "2026.backup").write_text("meta: {}\n")

    years = year_config.available_years()

    assert years == (2024, 2025, 2026)


@pytest.mark.parametrize("year", year_config.available_years())
@pytest.mark.parametrize("category", ["pension", "freelance", "agricultural", "other"])
def test_general_income_categories_share_article_15_scale(
    year: int, category: str
) -> None:
    """Article 15 KFE sets one scale for wage, pension and business income.

    The calculator taxes all general income on the employment brackets, so a
    per-category scale that differs would only mislead the bracket summaries.
    """

    config = year_config.load_year_configuration(year)

    assert getattr(config, category).brackets == config.employment.brackets


def _valid_rules() -> dict[str, object]:
    return {
        "age_reference_year": 2026,
        "youth_bands": {"under_25": 25, "age26_30": 30},
        "youth_relief_categories": ["employment"],
        "residency_transfer_taxable_share": 0.5,
        "salary_credit": {
            "income_categories": ["employment"],
            "reduction_threshold": 12000,
            "reduction_step": 1000,
            "reduction_per_step": 20,
            "shared_across_general_income": False,
        },
    }


def test_rules_parse_with_defaults() -> None:
    raw = _valid_rules()
    del raw["age_reference_year"]

    rules = year_config._parse_rules(2025, raw)

    assert rules.age_reference_year == 2025
    assert rules.youth_bands == (("under_25", 25), ("age26_30", 30))
    assert rules.max_birth_year_with_income is None
    assert rules.salary_credit.shared_across_general_income is False


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("youth_relief_categories",), ["employment", "rental"]),
        (("youth_relief_categories",), ["employment", "employment"]),
        (("youth_bands",), {"under_25": 30, "age26_30": 25}),
        (("youth_bands",), {}),
        (("residency_transfer_taxable_share",), 1.5),
        (("residency_transfer_taxable_share",), -0.1),
        (("salary_credit", "reduction_step"), 0),
        (("salary_credit", "reduction_threshold"), "12000"),
        (("age_reference_year",), 2026.0),
        (("max_birth_year_with_income",), "2025"),
        (("salary_credit", "shared_across_general_income"), None),
        (("salary_credit", "shared_across_general_income"), "false"),
    ],
)
def test_rules_reject_invalid_values(path: tuple[str, ...], value: object) -> None:
    raw = _valid_rules()
    target = raw
    for key in path[:-1]:
        target = target[key]  # type: ignore[assignment]
    target[path[-1]] = value  # type: ignore[index]

    with pytest.raises(year_config.ConfigurationError):
        year_config._parse_rules(2026, raw)


def test_rules_section_is_required() -> None:
    with pytest.raises(year_config.ConfigurationError):
        year_config._parse_rules(2026, None)
