"""Configuration payloads bundled into the frontend (client-config.generated.js)."""

from shutil import copy2
from unittest.mock import patch

import pytest
import yaml

from greektax.backend.config import year_config
from greektax.backend.config.client_payloads import (
    application_metadata,
    deduction_hints,
    investment_categories,
    years_payload,
)
from greektax.backend.version import get_project_version


def test_application_metadata() -> None:
    assert application_metadata() == {"version": get_project_version()}


def test_years_payload() -> None:
    payload = years_payload()
    years = payload["years"]
    assert any(entry["year"] == 2024 for entry in years)
    assert any(entry["year"] == 2025 for entry in years)
    assert any(entry["year"] == 2026 for entry in years)
    assert payload["default_year"] == 2026

    current_year = next(entry for entry in years if entry["year"] == 2026)
    transition_year = next(entry for entry in years if entry["year"] == 2025)
    legacy_year = next(entry for entry in years if entry["year"] == 2024)

    employment_meta = current_year["employment"]
    assert employment_meta["payroll"]["default_payments_per_year"] == 14
    assert 12 in employment_meta["payroll"]["allowed_payments_per_year"]
    assert employment_meta["contributions"]["employee_rate"] >= 0
    toggles = current_year["meta"].get("toggles", {})
    assert set(toggles.keys()).issuperset({"presumptive_relief", "tekmiria_reduction"})

    pension_meta = current_year["pension"]
    assert pension_meta["payroll"]["allowed_payments_per_year"]
    assert pension_meta["contributions"]["employer_rate"] >= 0

    rental_meta = current_year["rental"]
    assert rental_meta["brackets"][0]["rate"] == pytest.approx(0.15)
    assert rental_meta["brackets"][1]["upper"] == 24_000
    assert rental_meta["brackets"][1]["rate"] == pytest.approx(0.25)
    assert rental_meta["brackets"][2]["upper"] == 36_000

    freelance_meta = current_year["freelance"]
    trade_fee = freelance_meta["trade_fee"]
    assert trade_fee["standard_amount"] == 0
    assert trade_fee.get("reduced_amount") in {None, 0}
    assert trade_fee.get("sunset") is None
    assert trade_fee.get("newly_self_employed_reduction_years") is None
    assert freelance_meta.get("pending_contribution_update") is False
    transition_trade_fee = transition_year["freelance"]["trade_fee"]
    assert transition_trade_fee["standard_amount"] == 0
    assert transition_trade_fee["fee_sunset"] is False
    assert transition_trade_fee.get("newly_self_employed_reduction_years") is None
    categories = freelance_meta["efka_categories"]
    assert isinstance(categories, list)
    general_category = next(
        category for category in categories if category["id"] == "general_class_1"
    )
    # e-EFKA circular 6/2026.
    assert general_category["monthly_amount"] == pytest.approx(250.77)
    assert general_category["estimate"] is False

    warnings = current_year["warnings"]
    assert isinstance(warnings, list) and warnings
    warning_ids = {entry["id"] for entry in warnings}
    assert "employment.partial_year_review" in warning_ids
    assert all(
        entry not in warning_ids
        for entry in ("config.pending_deduction_updates", "freelance.trade_fee_sunset")
    )

    legacy_trade_fee = legacy_year["freelance"]["trade_fee"]
    assert legacy_trade_fee["standard_amount"] > 0
    assert "sunset" in legacy_trade_fee
    assert legacy_trade_fee["sunset"]["year"] == 2025
    assert legacy_trade_fee["sunset"]["description_key"]
    modern_trade_fee = current_year["freelance"]["trade_fee"]
    assert modern_trade_fee["standard_amount"] == 0
    assert modern_trade_fee.get("sunset") is None
    assert modern_trade_fee["fee_sunset"] is True


def test_years_payload_discovers_new_config_file(tmp_path) -> None:
    original_directory = year_config.CONFIG_DIRECTORY
    for filename in ("2024.yaml", "2025.yaml"):
        copy2(original_directory / filename, tmp_path / filename)

    new_year_path = tmp_path / "2030.yaml"
    copy2(original_directory / "2025.yaml", new_year_path)
    config = yaml.safe_load(new_year_path.read_text())
    config["year"] = 2030
    config.setdefault("meta", {})["year"] = 2030
    new_year_path.write_text(
        yaml.safe_dump(config, sort_keys=False, allow_unicode=True)
    )

    year_config.load_year_configuration.cache_clear()
    with patch.object(year_config, "CONFIG_DIRECTORY", tmp_path):
        year_config.load_year_configuration.cache_clear()
        payload = years_payload()

    year_config.load_year_configuration.cache_clear()

    years = payload["years"]
    discovered = {entry["year"] for entry in years}
    assert {2024, 2025, 2030}.issubset(discovered)
    assert payload["default_year"] == 2030


def test_investment_categories() -> None:
    payload = investment_categories(2024, "el")
    assert payload["locale"] == "el"
    categories = {item["id"]: item for item in payload["categories"]}
    assert "dividends" in categories
    assert categories["dividends"]["label"] == "Μερίσματα"


def test_investment_categories_missing_year() -> None:
    with pytest.raises(FileNotFoundError):
        investment_categories(1999, "en")


def test_deduction_hints() -> None:
    payload = deduction_hints(2024, "el")
    assert payload["locale"] == "el"

    hints = {hint["id"]: hint for hint in payload["hints"]}
    assert "dependents.children" in hints
    children_hint = hints["dependents.children"]
    assert children_hint["input_id"] == "children-input"
    assert children_hint["description"].startswith("Καταμετρήστε")
    assert "allowances" not in children_hint or not children_hint["allowances"]
