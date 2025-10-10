# Configuration Schema Modernisation Notes

## Objectives

- Define a single source of truth for tax-year configuration files that can be validated and introspected.
- Support both legacy flat rate tables (2024–2025) and future multi-dimensional rate matrices (2026+) without bespoke loaders.
- Provide metadata and feature-flag support so downstream services can conditionally enable behaviour.

## Proposed schema structure

1. **Manifest layer** – Introduce `config/manifest.yaml` listing supported years, file paths, and lifecycle metadata (`status`, `introduced`, `sunset`). Consumers load the manifest first to avoid filesystem scans.
2. **Year document root** – Normalise root keys to `{meta, toggles, income, deductions, hints, warnings}` with explicit optional sections. Each YAML must declare `meta.schema_version` for migrations.
3. **Income categories** – Model each income stream as an object with `payroll`, `contributions`, `tax_brackets`, and optional `credits`. Brackets accept either:
   - `rate` (float) for legacy entries, or
   - `rates` object describing matrices keyed by demographic dimension plus optional `reduction_factor` descriptors.
   Validation enforces mutual exclusivity.
4. **Credits and allowances** – Extract hints/allowances into dedicated sections referencing translation keys by ID. Provide structured arrays for `allowances`, each with `label_key`, `description_key`, `thresholds`.
5. **Toggles and provisional data** – Reserve `meta.flags` for consumer guidance (`provisional: true`, `requires_confirmation: ["tax_credit"]`). Add `toggles` for runtime feature flags (e.g., `tekmiria_reduction`).
6. **References** – Allow optional `documentation` blocks with `url` and `label_key` to link to supporting material.

## Validation approach

- Implement Pydantic models mirroring the schema with custom validators handling union types (`rate` vs `rates`).
- Provide `greektax.backend.config.loader.load_year(year: int)` returning the parsed model plus raw dict for backward compatibility.
- Update `scripts/validate_config.py` to expose CLI options (`--year`, `--manifest-only`) and surface structured error messages.
- Add tests covering both schema versions and cross-file consistency (e.g., ensure manifest references actual files).

## Migration considerations

- Write codemods/templates to convert 2024/2025 brackets into explicit objects referencing schema defaults.
- Introduce compatibility helpers translating legacy field names (e.g., `trade_fee.sunset`) into structured `sunset` objects.
- Provide documentation describing the schema evolution path and expected release timeline.
