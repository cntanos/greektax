# Configuration and Tooling Inventory (Discovery)

## Tax year YAML files

| File | Status | Notable contents | Redundancies / Gaps |
| --- | --- | --- | --- |
| `src/greektax/backend/config/data/2024.yaml` | Draft (meta.status) | Baseline brackets for employment, pension, freelance, agricultural, other, rental, investment; detailed hints and warnings. | Shares identical bracket tables and deduction hints with 2025; no explicit toggles/manifest references. |
| `src/greektax/backend/config/data/2025.yaml` | Final | Mirrors 2024 structure with updated contribution rates and EFKA amounts; trade fee zeroed out. | Retains full hint set even when fields are unchanged; lacks metadata for post-trade-fee transition; no manifest entry describing supported years. |
| `src/greektax/backend/config/data/2026.yaml` | Draft | Introduces nested rate matrices by dependants and age groups, provisional credits, and toggle flags. | Structure diverges from 2024/2025 (rates nested vs. flat); missing allowances/hints for deductions except dependents; pending confirmation flags but no consumer guidance. |

**Gaps:** No YAML before 2024 or manifest describing deprecated years; overlapping hints between 2024/2025 create maintenance duplication; 2026 schema not backwards compatible with loaders expecting flat `rate` fields.

## Repository scripts (`scripts/`)

| Script | Purpose | Notes | Redundancies / Gaps |
| --- | --- | --- | --- |
| `embed_translations.py` | Embeds `src/greektax/translations/*.json` frontend sections into a generated JS asset. | Writes to `src/frontend/assets/scripts/translations.generated.js`; lacks CLI options or diff detection. | No validation of placeholder usage; duplicates logic from localisation build steps once a module bundler is introduced. |
| `performance_snapshot.py` | Measures backend calculation timings, asset bundle sizes, and basic accessibility metrics. | Hard-coded sample payload and asset paths; imports backend service via path hack. | Not wired into CI; HTML scanner only counts ARIA usage (no assertions); partly overlaps with `docs/performance_baseline.md`. |
| `validate_config.py` | Wrapper around `greektax.backend.config.validator.main`. | Bootstraps `src` path for direct execution. | Only proxies to module; lacks CLI for selecting specific years; duplicates entrypoint logic once packaging is standardised. |

**Gaps:** No README or help text for scripts; no task runner integration; no script to diff translation keys or manifest supported years.

## Translation catalogues (`src/greektax/translations/`)

| File | Locales / Sections | Notes | Redundancies / Gaps |
| --- | --- | --- | --- |
| `en.json` | `backend` and `frontend` namespaces for English. | Comprehensive backend hints; frontend actions/messages; lacks schema metadata. | Contains keys not referenced in current YAML (e.g., `summary.refund_reduction` duplicates `summary.refund_due`). |
| `el.json` | Greek translation mirroring `en.json`. | Provides Greek equivalents but backend section includes placeholders for future hints. | Some backend keys present without frontend equivalents; no automation to ensure parity between locales. |
| `__init__.py` | Declares package exports. | Empty placeholder for namespace package. | No catalogue manifest or helper utilities. |

**Gaps:** Only English and Greek locales provided; no translation manifest for supported languages; no tooling to detect unused keys or keys missing across locales; frontend embed script silently drops backend section.
