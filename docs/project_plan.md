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

## Sprint 13 (Current)

**Objectives**
- Align the calculator experience with documented Greek payroll and social
  security rules, including fixed payroll frequencies and automatic EFKA
  contribution handling.【F:docs/ui_improvement_plan.md†L13-L36】
- Expand inputs and summaries to support gross-to-net and net-to-gross flows,
  deductions, dependent children, and additional income categories called for in
  the requirements.【F:docs/ui_improvement_plan.md†L38-L73】
- Establish configuration-driven year management, trade-fee parameters, and
  extensibility hooks so annual updates require minimal code churn.【F:docs/ui_improvement_plan.md†L75-L118】

**Planned Deliverables**
- Employment and pension UI slices with payroll-frequency selectors, gross/net
  toggles, and EFKA breakdown displays wired to backend calculation changes.
- Freelance and deductions experiences that capture EFKA category selections,
  trade-fee modifiers, and legally recognised deduction inputs with validation.
- Dynamic section toggles, agricultural/other income capture, and year-aware
  configuration plumbing surfaced throughout the interface and API contract.

**Next Steps (Preview of Sprint 14)**
- Validate implemented EFKA, deduction, and payroll features with domain
  specialists and update regression scenarios for edge cases (e.g., partial
  years, exempt professions).
- Explore extending configuration coverage to planned legislative changes (e.g.,
  trade-fee sunset) and prototype alerts for missing configuration data.
- Investigate localisation refinements and guidance assets (videos, tooltips) to
  reinforce the expanded data-entry workload introduced in Sprint 13.

> _This plan is updated at the end of each sprint to capture accomplishments_
> _and upcoming milestones._
