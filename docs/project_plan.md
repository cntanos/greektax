# GreekTax Development Plan

## Vision
GreekTax will provide an unofficial, bilingual (Greek/English) tax calculation
tool for individuals in Greece. The project prioritises accuracy, clarity, and
maintainability. Development will proceed iteratively using epics and sprints to
deliver user value in incremental, testable slices.

## Epics Overview

1. **Core Tax Engine**
   - Establish domain models for income categories, deductions, and
     contributions.
   - Implement year-based configuration management and calculation pipelines.
   - Provide comprehensive automated test coverage and documentation.

2. **User Experience & Localization**
   - Build bilingual UI components with responsive layouts and accessibility
     compliance.
   - Implement localization utilities across front-end and back-end layers.
   - Ensure high-fidelity error handling and user guidance.

3. **Extended Tax Obligations & Reporting**
   - Support optional modules such as VAT, ENFIA, and luxury tax inputs.
   - Deliver printable or shareable summaries and export formats.
   - Validate calculations against real-world scenarios.

4. **Operations & Quality Assurance**
   - Automate testing (unit, integration, end-to-end) and quality gates
     (linting, type checking).
   - Provide deployment guides, observability hooks, and maintenance playbooks.
   - Facilitate contributor onboarding with comprehensive documentation.

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
- Regression scenarios and unit tests validating VAT/ENFIA obligations within
  the calculation engine.

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

## Sprint 17 (Current)

**Objectives**
- Integrate the configuration validation tooling into contributor workflows and
  continuous integration to surface actionable feedback early.
- Refine lightweight, privacy-preserving scenario export concepts that extend
  local persistence without introducing server storage.
- Plan moderated usability reviews focused on localisation guidance and the new
  results visualisations to drive the next wave of refinements.

**Planned Deliverables**
- CI-ready configuration validation checks plus contributor documentation on
  interpreting and fixing failures.
- Updated prototypes or design notes detailing offline-friendly scenario export
  flows and accessibility considerations.
- Usability test scripts and localisation checklists ready for stakeholder
  sessions covering the enhanced calculator experiences.

> _This plan is updated at the end of each sprint to capture accomplishments_
> _and upcoming milestones._
