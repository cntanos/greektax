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

### Calculation engine mode

`GREEKTAX_ENGINE_MODE` chooses where calculations run. The same script writes it into the page as `<meta name="greektax-engine" content="...">`:

- `server` (default, or unset): the page posts each calculation to the API, as before.
- `shadow`: the page posts to the API and also runs the client-side engine (`assets/scripts/engine/`). It shows the server's result as soon as it arrives, without waiting for the client engine, and afterwards logs `[GreekTax shadow] client engine matches the server`, or a warning listing the differing fields, to the browser console. Nothing else is sent anywhere.
- `client`: the page runs the client-side engine only and makes no calculation request.

Any other value makes the script exit with an error. Set it in `~/.greektax-deploy.env` on the cPanel host (sourced by `.cpanel.yml`) and redeploy.

In `shadow` and `client` modes the page downloads the client engine (about 109 KB of JavaScript before compression) while it is idle after loading; `server` mode never downloads it.

For cPanel-based deploys, invoke the script from `.cpanel.yml` (or the equivalent post-deploy hook) after the static files have been copied into the docroot. CORS must permit the frontend origin → backend origin call; verify with a manual cross-origin fetch before relying on the deployed page.

## Year configuration refreshes

When introducing or updating filing years in `src/greektax/backend/config/data/*.yaml`:

1. Update the year YAML file. Year-specific calculation rules that are not rate tables (youth age bands and reference year, which categories get youth relief, the residency-transfer share, the salary-credit reduction and sharing) live in its `rules` section; the engine has no year-specific branches in code.
2. Run `python scripts/validate_config.py`.
3. Run `python scripts/build_client_config.py` to rebuild the bundled frontend configuration (`src/frontend/assets/scripts/data/client-config.generated.js`). Rebuild it as well after translation or version changes; `pytest` fails while it is stale.
4. Run `python scripts/generate_parity_fixtures.py` and review the diff in `tests/data/parity/`. Every changed expectation should be an intended consequence of the YAML change; `pytest` fails while the fixtures are stale. The client-side engine must then still match them: run `npm run test:frontend`.
5. Run `pytest`.
6. Document any user-facing copy impacts in the i18n workflow doc.

For localisation details, use [`docs/i18n.md`](i18n.md) directly.
