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

## Sprint 0 (Current)

**Objectives**
- Establish repository structure for front-end, back-end, and configuration
  assets.
- Configure development tooling (Python, Flask, pytest, linting) for use in
  Visual Studio Code.
- Document the iterative delivery plan and placeholder TODOs for upcoming work.

**Deliverables**
- Source tree scaffold with TODO markers for pending implementation items.
- Initial automated test placeholders to verify wiring and enable CI pipelines.
- Documentation updates (this plan, README references) enabling new
  contributors to understand the roadmap.

**Next Steps (Preview of Sprint 1)**
- Flesh out year-configuration schema and validation logic.
- Implement foundational tax calculation routines for employment and freelance
  income, backed by unit tests.
- Begin localization groundwork (resource files, language toggle strategy).

> _This plan will be updated at the conclusion of each sprint to reflect
> completed work and upcoming milestones._
