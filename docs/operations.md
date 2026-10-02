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

## Deployment

The site is static: `.cpanel.yml` copies `src/frontend/` into the cPanel docroot and then runs

```bash
python3 scripts/configure_frontend.py --target "$DEPLOYPATH/index.html"
```

which appends `?v=<hash>` to every local script reference (the `<script>` tags in `index.html` and every relative `import`, including the engine's dynamic `import()`), so browsers fetch new files after each deploy instead of serving stale ones. The hash only depends on the scripts' content, so re-running it is harmless.

`index.html` carries a Content-Security-Policy meta tag: scripts only from the site and the pinned Plotly build on `cdn.plot.ly`, no network requests (`connect-src 'none'`), no form submissions and no `eval`. A new external script or any network call needs a matching policy change, and `tests/frontend/contentSecurityPolicy.test.js` fails until it is made. If the host (cPanel/WordPress) also sends a CSP header, the browser applies both, so the stricter rules win.

There is no server-side component and no deploy-time configuration. Calculations run in the browser with the bundled engine (`assets/scripts/engine/`), which `ui/calculationRunner.js` downloads once the page is idle; no input leaves the device.

## Year configuration refreshes

When introducing or updating filing years in `src/greektax/backend/config/data/*.yaml`:

1. Update the year YAML file, citing the source of each changed figure in a YAML comment (see [`docs/reference/tax_rules_2025_2026.md`](reference/tax_rules_2025_2026.md) for the current ones). Year-specific calculation rules that are not rate tables (youth age bands and reference year, which categories get youth relief, the residency-transfer share, which income the salary credit covers and how it is reduced) live in its `rules` section; the engine has no year-specific branches in code.
2. Run `python scripts/validate_config.py`.
3. Run `python scripts/build_client_config.py` to rebuild the bundled frontend configuration (`src/frontend/assets/scripts/data/client-config.generated.js`). Rebuild it as well after translation or version changes; `pytest` fails while it is stale.
4. Run `python scripts/generate_parity_fixtures.py` and review the diff in `tests/data/parity/`. Every changed expectation should be an intended consequence of the YAML change; `pytest` fails while the fixtures are stale. The JavaScript engine must then still match them: run `npm run test:frontend`.
5. Run `pytest`.
6. Document any user-facing copy impacts in the i18n workflow doc.

For localisation details, use [`docs/i18n.md`](i18n.md) directly.
