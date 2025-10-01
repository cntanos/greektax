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

## Sprint 3 (Current)

**Objectives**
- Expose the calculation engine through a REST endpoint with structured error
  handling.
- Provide a language toggle on the front-end that propagates the selected
  locale to the API.
- Establish regression fixtures that exercise representative taxpayer profiles.

**Deliverables (to date)**
- Flask blueprint serving `POST /api/v1/calculations` with localisation-aware
  responses and JSON error envelopes.
- Front-end preview controls that persist locale preference and request
  translated summaries from the backend.
- Regression scenario catalogue consumed by integration tests for ongoing
  validation.

**Next Steps (Preview of Sprint 4)**
- Add REST endpoints for configuration metadata (available years, investment
  categories) to support dynamic UI elements.
- Connect core form inputs on the front-end to the API and render the returned
  breakdown.
- Provide printable/exportable summaries and broaden scenario coverage to VAT
  and ENFIA inputs.

> _This plan is updated at the end of each sprint to capture accomplishments_
> _and upcoming milestones._
