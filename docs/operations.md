# Operational Workflows Index

Use this page as a routing index. Detailed procedures live in their canonical documents to avoid duplication.

## Workflow pointers

- **Localisation updates** → [`docs/i18n.md`](i18n.md)
- **Performance baselines** → [`docs/performance_baseline.md`](performance_baseline.md)
- **Architecture and system boundaries** → [`docs/architecture.md`](architecture.md)
- **UI review loops** → [`docs/ui_improvement_plan.md`](ui_improvement_plan.md)
- **Contribution process** → [`docs/contributing.md`](contributing.md)

## Quality gate command

Run the full quality gate with a single command:

```bash
python scripts/quality.py
```

This command runs linting, type-checking, dead-code/static checks, security scanning,
frontend static checks, and bundle-size budgets.

## Quality thresholds and remediation

### Accepted thresholds

- **Bundle-size budgets** (`python scripts/check_bundle_size.py`):
  - `src/frontend/assets/scripts/main.js` ≤ **2,048 bytes**
  - `src/frontend/assets/styles/main.css` ≤ **60,000 bytes**
- **Dead-code confidence** (`vulture src tests --min-confidence 100 --ignore-names cls,__context,package`):
  - Any report at confidence 100 is treated as actionable and fails CI.
- **Dependency vulnerabilities** (`pip-audit -r requirements.txt -r requirements-dev.txt`):
  - Zero known vulnerabilities in the resolved environment.
- **Outdated dependency report** (`pip list --outdated`):
  - Informational report in CI; does not fail builds by itself.

### Remediation path

1. Reproduce the failing check locally with `python scripts/quality.py`.
2. For bundle budget failures:
   - remove unused selectors/imports and simplify JS bootstrapping, then rerun `python scripts/check_bundle_size.py`.
   - if growth is intentional, document why in PR and update thresholds in `scripts/check_bundle_size.py`.
3. For dead-code failures:
   - remove unreachable functions/branches, or wire the code into runtime/tests so it is genuinely used.
4. For `pip-audit -r requirements.txt -r requirements-dev.txt` failures:
   - upgrade the vulnerable dependency in `pyproject.toml`, regenerate requirements via `python scripts/sync_requirements.py`, and rerun quality checks.
   - if no safe upgrade exists, document temporary risk acceptance in the PR with a follow-up issue.
5. For outdated dependencies:
   - prioritize security and runtime-critical packages first, then batch lower-risk updates in scheduled maintenance PRs.

## Year configuration refreshes

When introducing or updating filing years in `src/greektax/backend/config/data/*.yaml`:

1. Update the year YAML file.
2. Run `python scripts/validate_config.py`.
3. Run `pytest`.
4. Document any user-facing copy impacts in the i18n workflow doc.

For localisation details, use [`docs/i18n.md`](i18n.md) directly.
