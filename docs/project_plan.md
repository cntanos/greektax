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

## Sprint 2 (Current)

**Objectives**
- Broaden the calculation engine to cover pension, rental, and investment
  income categories with aggregated summaries.
- Expand the localization catalogue for the newly supported categories.
- Publish an API contract and improve error messaging for validation failures.

**Deliverables**
- Year configuration extended with pension, rental, and investment sections for
  2024.
- Calculation service enhancements producing bilingual breakdowns for all
  categories alongside unit tests for new scenarios.
- API contract documentation capturing request validation rules and
  response structure.

**Next Steps (Preview of Sprint 3)**
- Implement REST endpoints that expose the calculation service and return
  structured validation errors.
- Begin integrating the front-end language toggle with backend localization.
- Introduce scenario fixtures that mirror representative taxpayer profiles for
  regression testing.

> _This plan is updated at the end of each sprint to capture accomplishments_
> _and upcoming milestones._
