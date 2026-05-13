# Operational Workflows Index

Use this page as a routing index. Detailed procedures live in their canonical documents to avoid duplication.

## Workflow pointers

- **Localisation updates** → [`docs/i18n.md`](i18n.md)
- **Performance baselines** → [`docs/performance_baseline.md`](performance_baseline.md)
- **Architecture and system boundaries** → [`docs/architecture.md`](architecture.md)
- **UI review loops** → see [`docs/archive/ui_improvement_plan.md`](archive/ui_improvement_plan.md) for the Sprint 16 visual-polish checklist (delivered; retained for context).
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

## Frontend API base injection

The source `src/frontend/index.html` stays deployment-agnostic: it ships with no `<meta data-api-base>` tag and `resolveApiBase()` falls back to the same-origin `/api/v1`. Cross-origin deployments (where the static frontend and the Flask backend live on different hosts) inject the meta tag at deploy time with `scripts/configure_frontend.py`:

```bash
GREEKTAX_API_BASE=https://<account>.pythonanywhere.com/api/v1 \
    python scripts/configure_frontend.py --target /path/to/served/index.html
```

The injection sits inside `<!-- @greektax/api-base:start --> ... <!-- @greektax/api-base:end -->` markers, so the script is idempotent — re-running it replaces any previous block. Running it with `GREEKTAX_API_BASE` unset or empty removes any prior injection, returning the file to its same-origin default. Keep the backend host value out of the repo: source it from a deploy-time environment variable, a non-committed config file, or a CI secret.

For cPanel-based deploys, invoke the script from `.cpanel.yml` (or the equivalent post-deploy hook) after the static files have been copied into the docroot. CORS must permit the frontend origin → backend origin call; verify with a manual cross-origin fetch before relying on the deployed page.

## Year configuration refreshes

When introducing or updating filing years in `src/greektax/backend/config/data/*.yaml`:

1. Update the year YAML file.
2. Run `python scripts/validate_config.py`.
3. Run `pytest`.
4. Document any user-facing copy impacts in the i18n workflow doc.

For localisation details, use [`docs/i18n.md`](i18n.md) directly.
