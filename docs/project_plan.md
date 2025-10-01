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

## Sprint 4 (Current)

**Objectives**
- Surface configuration metadata (available years, investment categories) for
  dynamic UI rendering.
- Wire the primary calculator form to the API, including printable/exportable
  summaries.
- Expand automated coverage to VAT and ENFIA obligations alongside existing
  income scenarios.

**Deliverables (to date)**
- REST endpoints exposing available tax years and locale-aware investment
  categories.
- Interactive calculator UI tied to the backend with download and print helpers
  plus investment metadata hydration.
- Regression scenarios and unit tests validating VAT/ENFIA obligations within
  the calculation engine.

**Next Steps (Preview of Sprint 5)**
- Introduce endpoints for year metadata beyond investment categories (e.g.
  deductible catalogues) to power richer UI hints.
- Implement client-side validation and localisation for the expanded form
  fields.
- Deliver shareable/print-ready summary layouts (PDF or HTML) and broaden
  regression coverage to luxury tax and VAT edge cases.

> _This plan is updated at the end of each sprint to capture accomplishments_
> _and upcoming milestones._
