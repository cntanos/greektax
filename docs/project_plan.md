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

## Sprint 1 (Current)

**Objectives**
- Provide validated, structured configuration for 2024 tax rules.
- Deliver the first slice of the tax engine covering employment and freelance
  income, including statutory credits and the trade fee.
- Introduce localization plumbing to support bilingual responses.

**Deliverables**
- Dataclass-backed configuration loader with schema validation and caching.
- 2024 YAML configuration featuring progressive brackets, tax credits, and
  trade-fee parameters.
- Calculation service producing bilingual summaries for employment and
  freelance scenarios with unit test coverage.
- Localization catalogue supporting English and Greek labels for backend
  responses.

**Next Steps (Preview of Sprint 2)**
- Extend the calculation engine to cover rental, investment, and pension
  categories with aggregation logic.
- Expand localization resources and begin wiring front-end language toggles.
- Add payload validation errors suitable for API responses and document the
  request/response contract.

> _This plan is updated at the end of each sprint to capture accomplishments_
> _and upcoming milestones._
