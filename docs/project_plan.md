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

## Sprint 10 (Current)

**Objectives**
- Fortify the tax computation pipeline with broader scenario coverage and
  cross-checks against official guidance.
- Elevate the clarity and usability of the refreshed UI, ensuring the new
  monthly input model is intuitive for 12-, 14-, or custom-payment schedules.
- Document and validate the expanded gross/net breakdowns to sustain
  stakeholder confidence in calculation correctness.

**Planned Deliverables**
- Add high-fidelity regression cases for diverse employment arrangements,
  verifying allowances, credits, and edge conditions in the tax engine.
- Improve UI content hierarchy and labelling so gross, net, tax, and deduction
  figures remain immediately legible across locales and screen sizes.
- Extend API and front-end validation copy to clarify payment-per-year entry and
  surface additional derived metrics where helpful for decision-making.

**Next Steps (Preview of Sprint 11)**
- Broaden localisation QA with accessibility-focused audits and user testing of
  the revised summaries.
- Explore deeper support for supplementary income categories (e.g., bonuses or
  deferred compensation) informed by Sprint 10 findings.
- Monitor analytics and feedback channels to prioritise further usability or
  accuracy enhancements.

> _This plan is updated at the end of each sprint to capture accomplishments_
> _and upcoming milestones._
