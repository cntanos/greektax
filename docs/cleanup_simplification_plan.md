# Clean-up and Simplification Initiative

A cross-cutting roadmap to retire dead weight, reduce duplication, and make the
GreekTax codebase easier to maintain. The plan builds on the architecture and
workflow guides already published in the repository and emphasises incremental
refactors that keep the application deployable throughout the effort.

## Goals

1. **Eliminate redundant logic and assets** so the calculation API and static
   front-end expose a single, well-understood configuration surface.
2. **Flatten over-engineered abstractions** that slow contributors down without
   improving correctness.
3. **Update documentation and tooling** so new contributors land on the
   canonical sources and avoid outdated instructions.
4. **Tighten automated coverage** to protect the simplified code paths and
   streamline release preparation.

## Current pain points

- Large configuration objects in `year_config.py` implement bespoke caching and
  data classes that leak into the service layer, creating friction when adding a
  new tax year or trimming unused attributes. 【F:src/greektax/backend/config/year_config.py†L1-L119】
- The front-end bootstrap script handles localisation, storage, Plotly
  rendering, and theme toggles in a single file exceeding 1,400 lines, making it
  difficult to reason about dependencies or replace parts of the UI. 【F:src/frontend/assets/scripts/main.js†L1-L120】
- Documentation duplicates operational guidance across README, the
  documentation index, and workflow guides, creating drift despite the existing
  audit. 【F:README.md†L1-L120】【F:docs/documentation_audit.md†L1-L23】
- Tests cover many scenarios but lack a tidy ownership map; contributors must
  read multiple folders to know where to add new coverage, and parametrised
  fixtures drift from the production configuration.

## Workstreams

### 1. Configuration and data model clean-up

- Introduce a typed schema for tax year YAML using `pydantic` or `attrs` to
  replace the bespoke dataclasses and explicit validation helpers. The schema
  should surface defaults, deprecations, and feature flags directly in metadata
  so services do not need to duplicate guard clauses.
- Replace the implicit filesystem scanning logic with a manifest describing the
  supported years, making it easier to phase out obsolete data files.
- Split configuration responsibilities into dedicated modules: rates, credits,
  allowances, and metadata. Each module should expose serialisable plain data
  structures that the API can return without additional copying.
- Provide a small compatibility layer that adapts the new schema to the current
  calculation engine so the refactor can ship behind a feature flag.
- Update `scripts/validate_config.py` and associated tests to use the shared
  schema loader, ensuring validation fails fast when data drift occurs.

### 2. Calculation service simplification

- Map existing service responsibilities (request parsing, calculation, response
  formatting) and extract them into functions or classes with explicit inputs
  and outputs. `calculation_service.py` should delegate to pure calculation
  utilities that operate on the simplified configuration objects.
- Remove legacy code paths that supported deprecated share/export features and
  confirm the REST handlers only call actively maintained functions.
- Create reference scenarios that exercise the new API response shape and add
  regression tests confirming the numeric outputs match the current engine.
- Document the data flow from the request model to the response payload so
  future contributors can update individual steps without touching the entire
  service.

### 3. API surface consolidation

- Audit the route modules under `app/routes` and identify opportunities to
  collapse near-identical handlers (e.g., configuration endpoints that differ
  only by key) into parameterised utilities.
- Standardise error handling by introducing a shared `ProblemResponse` builder
  (or similar) that encapsulates localisation, HTTP status codes, and logging.
- Expose version discovery and health endpoints that reuse configuration
  metadata instead of hard-coding supported years in multiple places.
- Update OpenAPI or API contract documentation to reflect the simplified
  response shapes and error payloads.

### 4. Front-end restructuring

- Break the monolithic `main.js` file into modules that align with the major UI
  responsibilities: API client, state management, Sankey visualisation,
  localisation, and theming. Keep each module under 250 lines where practical
  and introduce a lightweight build step (e.g., Vite or Rollup) if bundling is
  required.
- Replace custom DOM traversal utilities with standard helpers (`querySelector`
  wrappers, dataset parsers) and remove unused feature toggles discovered during
  the audit.
- Introduce state snapshots with JSON schemas so saved calculator state remains
  compatible across releases and invalid entries fail gracefully.
- Add unit tests for the extracted modules using Vitest or Jest, and wire them
  into the existing CI workflow alongside Python tests.

### 5. Translation and localisation hygiene

- Consolidate translation metadata by generating TypeScript definition files
  (or JSON schemas) from the canonical catalogues in `src/greektax/translations`
  so both the API and front-end share key names.
- Replace the ad-hoc translation embedding script with a task that validates
  placeholder usage, detects unused keys, and reports drift between locales.
- Simplify locale detection on the front-end to a single source of truth while
  preserving overrides via `window.GREEKTAX_API_BASE` and storage keys.

### 6. Documentation and workflow consolidation

- Follow through on the documentation audit by trimming overlapping sections in
  `README.md` and pointing contributors to `docs/operations.md` for detailed
  workflows. Update the audit to note the resolved overlaps.
- Create a contributor playbook that links each code area (backend, front-end,
  configuration, translations) to the relevant tests and tooling, reducing the
  time required to onboard new maintainers.
- Ensure every script in `scripts/` has a short synopsis and usage example in
  the operations index or a dedicated README.
- Document the new configuration schema and translation pipeline so future
  changes stay aligned with the simplified architecture.

### 7. Testing and quality gates

- Reorganise the `tests/` directory to distinguish pure unit tests, API tests,
  and scenario-based regression suites. Introduce naming conventions that
  surface ownership (e.g., `test_config_*.py`, `test_api_*.py`).
- Add contract tests that load each YAML configuration and assert the presence
  of required fields, ensuring backwards compatibility with existing data.
- Integrate linters and type-checkers (`ruff`, `mypy`) into a single CI entry
  point and publish a `make verify` command to run the full suite locally.
- Track coverage trends and set thresholds aligned with the simplified modules,
  raising alerts when coverage dips below agreed targets.

## Execution phases

1. **Discovery (1 sprint)** – Finalise inventory of configuration files,
   redundant scripts, and unused translations. Produce design docs for the
   configuration schema and front-end modularisation.
2. **Core refactors (2–3 sprints)** – Ship the new configuration loader,
   simplify the calculation service, and modularise the front-end. Keep changes
   behind feature flags until regression tests pass.
3. **Surface alignment (1 sprint)** – Update API responses, documentation, and
   translation tooling to reflect the simplified internals. Remove the feature
   flags once parity is demonstrated.
4. **Stabilisation (ongoing)** – Monitor metrics, close out remaining cleanup
   tasks, and schedule quarterly reviews to prevent regressions.

## Success criteria

- New tax years can be added by updating configuration files and translations
  without editing Python or JavaScript code.
- Front-end bundle size decreases and module boundaries make ownership obvious.
- Documentation points to a single canonical source for each workflow, and the
  audit reflects the reduced duplication.
- CI pipelines complete faster with consolidated checks and maintainers report
  reduced onboarding time.
