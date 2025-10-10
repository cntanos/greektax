from greektax.backend.config.validator import (
    validate_all_years,
    validate_year_configuration,
)
from greektax.backend.config.year_config import load_year_configuration


def test_current_configurations_are_valid() -> None:
    results = validate_all_years()
    assert all(not issues for issues in results.values()), results


def test_validator_flags_invalid_payroll_default() -> None:
    config = load_year_configuration(2024)
    employment = config.employment.model_copy(
        update={
            "payroll": config.employment.payroll.model_copy(
                update={"default_payments_per_year": 99}
            )
        }
    )
    broken = config.model_copy(update={"employment": employment})

    errors = validate_year_configuration(broken)

    assert any("employment.payroll" in error for error in errors)


def test_validator_flags_invalid_contribution_rate() -> None:
    config = load_year_configuration(2024)
    employment = config.employment.model_copy(
        update={
            "contributions": config.employment.contributions.model_copy(
                update={"employee_rate": 1.5}
            )
        }
    )
    broken = config.model_copy(update={"employment": employment})

    errors = validate_year_configuration(broken)

    assert any("contributions" in error and "between 0 and 1" in error for error in errors)
