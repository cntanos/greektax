# GreekTax Development Plan

## Vision
- Deliver an unofficial, bilingual (Greek/English) tax calculation tool focused
  on accuracy, clarity, and maintainability.
- Iterate through measurable sprints so every increment is testable and tied to
  user value.
- Keep shared documentation aligned by updating the plan whenever we close a
  sprint or pivot scope.

## Documentation baseline
- Track overlapping or outdated guidance in [docs/documentation_audit.md](./documentation_audit.md) before touching shared
  docs so updates target the canonical source.
- Follow the conventions in [docs/documentation_style.md](./documentation_style.md) when drafting or revising
  documentation across the repository.

## Recent tax logic updates

- Charitable donations yield direct credits within the deduction engine while
  maintaining audit-friendly detail rows in the response payload.
- Trade fee handling reflects the latest filing guidance, only adding the
  charge for professions or start years that require it.
- Youth age derivation and the 2026 family tax credit ladder now mirror the
  ministry calculator, with youth relief determined from the 2026 reference
  year.
- Demographic inputs now require a birth year and automatically derive youth
  relief, removing manual age-band overrides and redundant confirmation
  toggles.
- The 2025 employment brackets now follow the uniform 9/22/28/36/44 schedule
  published by the ministry, matching the 2024 ladder without dependant or
  youth-specific adjustments.
- The 2026 wage and pension brackets mirror the confirmed youth and large-family
  relief schedule, while dependant credits, rental updates, and freelance EFKA
  bands remain provisional pending official circulars.
- Input validation now mirrors the ministry ranges by capping dependant children
  at 15, constraining birth years to the official window, and covering multiple
  youth scenarios with regression tests.

## Overview

1. **Functional requirements**
   - **1.1 Employment & Pension**
     - Maintain `employment` and `pension` income pipelines within the
       calculation service, including dependant credits and payroll-frequency
       validation aligned with the [API contract](./api_contract.md).
     - Surface year-specific warnings, allowances, and toggleable input groups
       in the UI, referencing the localisation keys defined in
       [`main.js`](../src/frontend/assets/scripts/main.js).
   - **1.2 Freelance & Trade Activity**
     - Calculate trade fees, EFKA classes, and engineer overrides using the
       `freelance` configuration schema and scenario coverage noted in recent
       sprints.
     - Provide guided activity-start workflows and metadata hints that mirror
       the UX flows documented in the [UI improvement plan](./ui_improvement_plan.md).
   - **1.3 Investment & Rental**
     - Support rental, capital-gains, and other investment categories with
       aggregated summaries, respecting provisional toggles in the 2026
       configuration files.
     - Keep the Sankey and summary views synchronised with calculation outputs
       so category totals stay localisation-ready.
   - **1.4 Shared Reporting & Validation**
     - Expose locale-aware configuration and calculation endpoints as defined in
       the [API contract](./api_contract.md).
     - Generate printable, shareable, or downloadable summaries only where they
       align with current calculator outputs, flagging legacy export paths as
       deprecated.

2. **Non-functional requirements**
   - **2.1 Localisation & Accessibility**
     - Preserve bilingual coverage with catalogues embedded in the static
       bundle and validated against the [UI improvement plan](./ui_improvement_plan.md).
     - Maintain accessibility checks, focus order, and responsive behaviour for
       all calculator views.
   - **2.2 Performance & Observability**
     - Monitor calculation latency using the performance snapshot utility and
       keep Sankey rendering responsive through deferred bootstrapping.
     - Capture telemetry hooks for navigation, validation friction, and share
       link expiry metadata.
   - **2.3 Quality & Tooling**
     - Enforce automated testing (unit, integration, regression) and linting to
       guard critical calculation paths.
     - Provide deployment, maintenance, and contributor onboarding guidance in
       lockstep with repository updates.

3. **Out-of-scope and deprecated**
   - **3.1 Legacy Share/Export Surfaces**
     - The retired Plotly sharing endpoint and PDF export tooling remain
       deprecated and are scheduled for removal once historical regression data
       is archived.
   - **3.2 Non-Integrated Tax Modules**
     - Future ENFIA or luxury tax expansions beyond documented scenarios are
       parked until the core calculator stabilises under the new configuration
       structure.
   - **3.3 External Data Imports**
     - Bulk data importers and third-party integrations (e.g., payroll
       providers) are excluded from the current roadmap and will be revisited in
       a later planning cycle.

## Sprint 0 (Completed)

**Highlights**
- Repository scaffolding for the Flask back-end, static front-end, and shared
  configuration assets.
- Development tooling (pytest, linting, VS Code configuration) verified via
  placeholder tests.
- Delivery roadmap documented to onboard contributors.

## Sprint 1 (Completed)

**Highlights**
- Schema-validated configuration loader with caching for 2024 tax rules.
- Initial calculation engine slice for employment and freelance income,
  including statutory credits and trade fee handling.
- Localization plumbing with English and Greek catalogues plus comprehensive
  unit coverage.

## Sprint 2 (Completed)

**Highlights**
- Calculation engine broadened to cover pension, rental, and investment income
  categories with aggregated summaries.
- Localization catalogue extended for the new income categories in both
  supported languages.
- API contract published with explicit validation guidance for future clients.

## Sprint 3 (Completed)

**Highlights**
- REST endpoint for tax calculations with structured error responses and
  localisation support.
- Locale-aware preview controls on the front-end persisting user preferences.
- Regression scenario catalogue underpinning integration coverage.

## Sprint 4 (Completed)

**Highlights**
- REST endpoints exposing available tax years and locale-aware investment
  categories.
- Interactive calculator UI tied to the backend with download and print helpers
  plus investment metadata hydration.
- Regression scenarios and unit tests validating ENFIA and luxury obligations
  within the calculation engine.

## Sprint 5 (Completed)

**Highlights**
- Extended configuration metadata endpoints with locale-aware deduction guidance
  for form tooling.
- Strengthened front-end localisation and validation across all calculator
  controls.
- Delivered the first iteration of shareable summaries with HTML exports and a
  luxury-tax-focused regression scenario.

## Sprint 6 (Completed)

**Highlights**
- Published richer deduction metadata, including allowance thresholds and a 2025
  regression configuration.
- Implemented share/export services supporting HTML, CSV, and PDF outputs with
  bundled fonts and localized labels.
- Enhanced the front-end with localized allowance rendering, share links, and
  download controls alongside expanded test coverage.

## Sprint 7 (Completed)

**Highlights**
- Hardened shareable summary storage with explicit expiry windows, capacity
  safeguards, and regression tests for repository lifecycle behaviour.
- Surfaced share-link expiry metadata through the API and localized UI
  messaging to set user expectations.
- Added regression and unit coverage validating repository expiration,
  capacity limits, and end-to-end summary expiry handling.

## Sprint 8 (Completed)

**Highlights**
- Consolidated the calculation engine architecture in preparation for upcoming
  accuracy improvements and UI refinements.
- Captured lessons learned from the initial share/export experiment to inform a
  leaner delivery scope focused on core tax functionality.
- Maintained localisation coverage and testing infrastructure to support rapid
  iteration in future sprints.

## Sprint 9 (Completed)

**Highlights**
- Removed the experimental sharing and PDF export surface area across the stack
  to simplify maintenance and reinforce the privacy stance.
- Normalised monthly salary handling in the calculation engine, yielding richer
  gross-versus-net summaries and per-payment insights.
- Refined the web UI to foreground key totals, accept monthly payment inputs,
  and keep CSV exports client-side for leaner usability.

## Sprint 10 (Completed)

**Highlights**
- Bolstered regression coverage for varied employment arrangements, aligning
  allowances and credits with documented tax guidance while capturing expected
  gross/net breakdowns for 12- and 14-payment schedules.
- Refined UI copy and labels so salary, tax, and deduction totals remain legible
  across locales, paving the way for deeper hierarchy and layout adjustments in
  upcoming sprints.
- Clarified payment-frequency validation flows in both the API contract and
  front-end messaging, reducing ambiguity for hybrid monthly/annual entry
  patterns.

## Sprint 11 (Completed)

**Highlights**
- Conducted wireframe explorations and content hierarchy audits that establish
  the target structure for a refreshed calculator summary with clearer gross,
  net, and obligation groupings.
- Delivered a UI improvement plan capturing responsive layout rules, design
  tokens, accessibility priorities, and localisation checks to guide upcoming
  implementation work.
- Partnered with localisation stakeholders and support to capture copy issues,
  telemetry hooks, and validation pain points feeding the next sprint backlog.

## Sprint 12 (Completed)

**Highlights**
- Shipped the reimagined calculator summary with progressive disclosure,
  localisation-ready formatting, and richer telemetry to monitor user
  navigation.
- Hardened validation and inline education for monthly versus annual entry,
  reducing user error reports across locales.
- Closed responsive and accessibility gaps through targeted layout tokens,
  focus-order fixes, and automated axe verification documented for future QA.

## Sprint 13 (Completed)

**Highlights**
- Implemented client-side persistence for calculator inputs with a two-hour
  expiry so refreshes within that window keep user data without transmitting it
  to the server.【F:src/frontend/assets/scripts/main.js†L503-L614】【F:src/frontend/assets/scripts/main.js†L831-L924】
- Updated the bilingual disclaimer copy to explain the local-storage behaviour
  and reinforce the project's privacy stance.【F:src/frontend/index.html†L24-L31】【F:src/frontend/assets/scripts/main.js†L20-L36】
- Refreshed the delivery roadmap to transition Sprint 14 into active execution
  with validation, configuration, and localisation priorities captured for the
  team.

## Sprint 14 (Completed)

**Highlights**
- Expanded the year configuration schema with trade-fee sunset metadata,
  structured warnings, and richer payroll options surfaced through the API and
  UI alerts.
- Delivered front-end affordances for year-specific guidance, including toggleable
  employment inputs, contextual alerts, and localisation updates spanning copy
  and validation hints.
- Broadened automated coverage with regression scenarios focused on partial-year
  employment, exemption handling, and pension payment frequencies alongside new
  integration tests for configuration warnings.

## Sprint 15 (Completed)

**Highlights**
- Localised EFKA category metadata on the calculator form so contributor-facing
  keys are replaced with translated labels and descriptive hints across
  languages.【F:src/frontend/assets/scripts/main.js†L70-L118】【F:src/frontend/assets/scripts/main.js†L1422-L1464】
- Filtered zero-value rows from detail cards to emphasise meaningful tax and
  contribution figures within each calculation component.【F:src/frontend/assets/scripts/main.js†L2056-L2116】
- Reworked the detail grid layout for consistent label/value pairing and better
  readability on narrow screens.【F:src/frontend/assets/styles/main.css†L400-L432】

## Sprint 16 (Completed)

**Highlights**
- Delivered a Plotly-powered Sankey diagram at the top of the results view so
  users can immediately see how each income stream divides between taxes,
  contributions, and take-home pay.
- Reworked the employment and pension toggle so the entire section now hides in
  tandem with the checkbox, keeping the form consistent with other optional
  income categories.
- Ensured language changes refresh the latest calculation output and year
  guidance without a full page reload, preserving localisation accuracy during
  review sessions.

## Sprint 17 (Completed)

**Highlights**
- Replaced the localisation preview form with header-level language and theme
  switches adopting CogniSys branding assets to reinforce bilingual controls at
  the top of the experience.
- Deepened the light and dark design token palette, tuned Sankey colours, and
  refreshed surface styling so the refreshed dark mode reads closer to CogniSys'
  visual identity.
- Hardened client-side persistence so investment income and other numeric
  inputs survive locale changes and refreshes, preventing silent value resets
  during review sessions.

## Sprint 18 (Completed)

**Highlights**
- Streamlined general-income processing with slot-based dataclasses and
  aggregated totals so repeated calculations reuse intermediate results while
  preserving localisation-rich detail output.【F:src/greektax/backend/app/services/calculation_service.py†L46-L84】【F:src/greektax/backend/app/services/calculation_service.py†L904-L1020】
- Deferred Plotly bootstrapping and staged theme re-renders to keep the Sankey
  diagram responsive on slower devices and to smooth the dark-mode transition
  experience.【F:src/frontend/assets/scripts/main.js†L24-L113】【F:src/frontend/assets/scripts/main.js†L2363-L2549】
- Enhanced the performance snapshot utility with richer timing telemetry so
  teams can track minimum, maximum, and average calculation durations alongside
  accessibility metadata.【F:scripts/performance_snapshot.py†L38-L88】

## Sprint 19 (Completed)

**Highlights**
  - Published 2024 through 2026 EFKA contribution classes for both general
    freelancers and engineers, exposing pension, health, auxiliary, and lump-sum
    breakdowns through the configuration APIs and localisation catalogues. The
    latest year is flagged as an estimate while the ministry finalises the
    schedule.【F:src/greektax/backend/config/data/2024.yaml†L118-L135】【F:src/greektax/backend/config/data/2026.yaml†L220-L333】【F:src/greektax/backend/app/localization/catalog.py†L54-L63】
- Reworked the freelance form to surface category summaries, trade-fee guidance,
  and a guided activity-start workflow that automatically determines reduced
  trade-fee eligibility.【F:src/frontend/index.html†L460-L541】【F:src/frontend/assets/scripts/main.js†L1788-L1897】
- Extended calculation and integration tests to cover engineer-specific
  auxiliary and lump-sum contributions while aligning expected values with the
  richer configuration metadata.【F:tests/unit/test_calculation_service.py†L292-L347】【F:tests/integration/test_config_endpoints.py†L26-L35】

## Sprints 20-24 (Completed)

**Highlights**
  - Codified mixed EFKA scenarios with manual overrides so engineer-specific
    auxiliary and lump-sum contributions are exercised in unit coverage and
    regression fixtures.【F:tests/unit/test_calculation_service.py†L667-L723】
  - Hardened configuration validation to flag payroll frequency gaps, EFKA data
    regressions, and trade-fee metadata issues before they reach production
  - Captured preliminary 2026 household brackets, dependant credits, and the
    rental mid-band reduction so downstream clients can prepare for the upcoming
    filing year while toggles remain in preview.【F:src/greektax/backend/config/data/2026.yaml†L5-L141】【F:src/greektax/backend/config/data/2026.yaml†L450-L520】
  deployments.【F:src/greektax/backend/config/validator.py†L1-L156】
- Maintained localisation and asset parity by re-embedding the bilingual
  catalogues into the static bundle whenever translations change, keeping the
  Flask responses and front-end shell aligned.【F:scripts/embed_translations.py†L1-L109】

## Sprint 25 (Current)

**Objectives**
- Update contributor-facing documentation to reflect the simplified Python/Flask
  stack and the removal of legacy PHP references.
- Refresh the project plan, requirements, and README to match the optimised code
  paths and the current roadmap.
- Consolidate redundant guidance so new contributors have a single up-to-date
  source of truth for setup, testing, and localisation workflows.

**Planned Deliverables**
- Revised requirements and repository guide aligning with the present
  architecture and calculation capabilities.【F:Requirements.md†L1-L118】
- Updated README and ancillary docs describing the supported APIs, translation
  pipeline, and calculation engine responsibilities.【F:README.md†L1-L140】
- Captured Sprint 25 outcomes and future documentation follow-ups in the project
  plan to keep the roadmap consistent with the cleaned codebase.

> _This plan is updated at the end of each sprint to capture accomplishments_
> _and upcoming milestones._
