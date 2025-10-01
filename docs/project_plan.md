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

## Sprint 8 (Current)

**Objectives**
- Provide a persistent storage option for shareable summaries that survives
  process restarts while remaining thread-safe under concurrent access.
- Improve PDF export fidelity for Greek locale output, including reliable font
  rendering and support for multi-page summaries.
- Gather structured user feedback on expiry messaging to refine UI cues and
  accessibility copy.

**Deliverables (to date)**
- Introduced a SQLite-backed share repository selectable via configuration and
  validated through concurrency-focused unit and integration tests.
- Embedded a Unicode-capable font pipeline for PDF generation with enhanced
  layout to better support Greek labels and multi-page detail sections.
- Added front-end feedback prompts and a backend collection endpoint capturing
  expiry clarity responses for iterative UI improvements.

**Next Steps (Preview of Sprint 9)**
- Analyse collected expiry feedback to refine localisation copy and visual
  cues.
- Prototype persistent share export cleanup jobs and operational dashboards.
- Expand PDF exports with richer tables, pagination cues, and locale-aware
  typography tuning.

> _This plan is updated at the end of each sprint to capture accomplishments_
> _and upcoming milestones._
