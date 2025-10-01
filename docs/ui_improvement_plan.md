# Sprint 13 UI & Tax Compliance Implementation Plan

## Purpose
Sprint 13 transforms the Sprint 12 UI refactor into a legally-aligned experience
that reflects the documented requirements and current Greek tax law. The work
prioritises controls for statutory payroll frequencies, EFKA contributions for
employees and freelancers, richer deduction capture, and configuration-driven
year management while safeguarding localisation, accessibility, and telemetry
foundations from earlier sprints.

## Regulatory & Requirements Drivers
- **Payroll cadence** – Greek employment contracts pay salary in fourteen
  instalments (twelve monthly payments plus Easter, summer, and Christmas
  bonuses). Interfaces must constrain payroll choices accordingly and update when
  legislation changes.【F:Requirements.md†L145-L177】
- **Social security contributions** – Employee EFKA contributions total 13.87 %
  of gross remuneration and apply to allowances, while freelancers select fixed
  monthly categories. The calculator must surface and respect these rules in both
  entry forms and summaries.【F:Requirements.md†L209-L235】【F:Requirements.md†L243-L276】
- **Deductions, dependants, and additional income** – Users require inputs for
  deductions, dependent children credits, agricultural/other income categories,
  and location-aware trade fees to mirror the official forms.【F:Requirements.md†L279-L348】【F:Requirements.md†L352-L426】
- **Year-specific configuration** – Tax brackets, credits, contribution rates,
  and trade-fee rules vary annually, demanding configuration-backed year
  selection and validation paths.【F:Requirements.md†L428-L476】

## Sprint 12 Learnings Informing This Sprint
- The refreshed summary layout improved comprehension but exposed gaps in payroll
  validation and EFKA transparency during feedback sessions.
- Inline education reduced hybrid monthly/annual confusion; extending that model
  to deductions and contribution logic will mitigate additional complexity.
- Telemetry now captures navigation and error events, supplying baselines for the
  expanded data-entry flows we introduce this sprint.

## Sprint 13 Goals
1. Provide employment and pension journeys that let users declare gross or net
   salaries, enforce lawful payroll frequencies, and display EFKA breakdowns for
   both employee and employer portions.
2. Deliver freelance, rental, investment, and agricultural sections that surface
   only when toggled on, capture EFKA categories or actual contributions, and
   apply location-aware trade fees.
3. Add structured deduction inputs, dependent-children selection, and year-aware
   validation that informs users when configuration data is missing or
   inconsistent.

## Key Workstreams
| Workstream | Focus | Primary Outputs |
| --- | --- | --- |
| Employment & pension compliance | Replace numeric payroll inputs with drop-down selectors, add gross/net toggles, and present EFKA contribution cards linked to the calculation engine. | Updated HTML/JS modules, localisation keys for payroll/legal copy, automated tests covering gross-to-net and net-to-gross cases. |
| Freelance contributions & trade fees | Model EFKA category selection, auxiliary fund capture, and trade-fee modifiers (location, newly self-employed) driven from configuration. | New configuration schema entries, client-side controls with validation, backend payload adjustments, and summary breakdown updates. |
| Dynamic income & deductions UX | Introduce income-type toggles, agricultural/other income sections, and deduction inputs with guardrails and contextual help. | Conditional rendering logic, translation updates, validation/error message matrix, and analytics dashboards for section usage. |
| Year management & resilience | Surface supported years from configuration, handle missing data gracefully, and document overrides for future tax-law changes. | Year selector UI, configuration integrity checks, error-handling patterns, and maintenance playbook entries. |

## Delivery Approach
1. **Iteration 1 – Employment & pension foundations (Days 1-3)**
   - Implement payroll dropdowns, gross/net selection state, and EFKA calculations
     for employment and pension flows.
   - Expose contribution breakdown cards and ensure localisation coverage for new
     legal copy.
2. **Iteration 2 – Freelance & income toggles (Days 4-6)**
   - Build EFKA category selectors, auxiliary contribution inputs, and trade-fee
     logic driven by configuration.
   - Add income-type toggles and conditional rendering for freelance,
     agricultural, rental, and investment sections.
3. **Iteration 3 – Deductions & dependants (Days 7-8)**
   - Ship deduction fields (donations, medical, education, insurance) with
     validation and dependent-children controls tied to tax credits.
   - Extend summaries to highlight deductions and credits applied.
4. **Iteration 4 – Year management & hardening (Days 9-10)**
   - Populate the year selector from available configuration files and add
     missing-config alerts.
   - Execute accessibility, localisation, and telemetry regression passes.

## Acceptance Criteria
- Employment payroll inputs are limited to legally supported frequencies and
  automatically recalculate EFKA contributions for gross and net scenarios.
- Freelance workflows compute contributions from category selections or manual
  overrides and apply the correct trade fee based on location and tenure.
- Deductions, dependants, and additional income sections are hidden by default,
  surface only when toggled, and feed accurate figures into the calculation
  payload and results summary.
- Year selection dynamically loads configuration assets, with user-facing errors
  when data is absent and automated tests covering at least two years.

## Dependencies & Risks
- Collaboration with tax-domain reviewers is required to confirm EFKA rates,
  trade-fee thresholds, and deduction limits per year.
- Calculation-service updates must land alongside UI changes to avoid
  inconsistent gross/net results.
- Additional fields increase translation volume; localisation review capacity may
  constrain release timing.

## Out of Scope
- Employer-side contribution payments beyond informational display.
- VAT, ENFIA, or other extended tax modules outside the documented requirements.
- Persisting user input; the calculator remains stateless and privacy-focused.

## References
1. TIES – Greece (KPMG), payroll frequency guidance.
2. OECD Tax and Benefit Policy Descriptions for Greece 2024, EFKA contribution
   breakdown.
3. Hellenic Ministry of Labour, freelancer contribution categories.
4. GreekTax Requirements document, deduction and configuration mandates.
