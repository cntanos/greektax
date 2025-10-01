# Sprint 16 UI Narrative & Visualisation Plan

## Purpose
Sprint 16 evolves the refreshed calculator shell into a cohesive visual
experience that foregrounds guidance, improves the Sankey flow legibility, and
makes colour choices and typography align with the new accessibility mandate in
the requirements.【F:Requirements.md†L96-L111】 The sprint closes the gap between
the documented visual expectations and the current prototype so that subsequent
iterations can focus on deeper calculation accuracy without revisiting core UI
polish.

## Requirements & Research Drivers
- **Visual communication mandate** – The requirements now call for colour-aware
  legends, accessible contrasts, and concise benefit callouts that orient users
  before they begin data entry.【F:Requirements.md†L96-L111】
- **Bilingual positioning** – Highlight cards and navigation copy must continue
  to respect localisation investments from prior sprints while presenting the
  new hero narrative succinctly in both languages.【F:src/frontend/assets/scripts/main.js†L20-L118】【F:src/frontend/assets/scripts/main.js†L241-L339】
- **Interactive clarity** – The Sankey diagram must display high-contrast
  connectors, hover states, and colour-coded groupings so that taxpayers can
  instantly understand how gross amounts flow into taxes, contributions, and net
  income.【F:src/frontend/assets/scripts/main.js†L2079-L2350】

## Sprint 15 Learnings Informing Sprint 16
- Persistent calculator storage improved resilience but exposed a visually flat
  landing experience and under-emphasised privacy messaging.
- The Sankey configuration relied on default Plotly styling, leading to low
  contrast links and no contextual legend during user testing sessions.
- Highlight cards that explain the calculator benefits were absent, causing
  onboarding sessions to spend extra time verbally describing the tool.

## Sprint 16 Goals
1. Introduce a headline hero treatment with localisation-aware highlight cards
   that summarise guided inputs, live localisation previews, and visual
   breakdowns.
2. Redesign the Sankey visualisation with explicit colour palettes, link
   contrast, and in-context legends that match accessibility targets.
3. Align core surfaces (cards, buttons, result summaries) with an updated design
   token set that reinforces hierarchy without sacrificing readability on small
   screens.
4. Document forward-looking UI next steps and risks so future sprints can plan
   deeper responsive behaviour and dark-theme validation.

## Key Workstreams
| Workstream | Focus | Primary Outputs |
| --- | --- | --- |
| Hero narrative & highlights | Craft the updated landing hero with eyebrow tag, headline, and three benefit highlight cards that localise cleanly. | Revised HTML structure, new localisation keys, and copy decks for both languages. |
| Sankey clarity | Apply explicit colour palettes, link widths, and legends so chart interactions are legible and screen-reader metadata remains accurate. | Plotly configuration updates, legend markup, accessibility notes, and smoke test scripts. |
| Design token refresh | Elevate cards, buttons, alerts, and summary panels with gradient surfaces and focus treatments that honour the new requirement. | Updated CSS variables, responsive adjustments, and regression screenshots documenting the visual baseline. |
| Documentation & roadmap | Capture outstanding UI follow-ups (dark mode, mobile nav, chart animations) and align with the overarching project plan. | Updated requirements annotations, project plan addendum, and open issues list. |

## Delivery Approach
1. **Iteration 1 – Hero & copy alignment (Days 1-2)**
   - Implement hero structure, highlight cards, and eyebrow tag with localisation
     coverage.
   - Validate copy with bilingual reviewers and ensure preview module still
     functions post-layout change.
2. **Iteration 2 – Sankey visualisation polish (Days 3-4)**
   - Apply colour tokens, legend markup, and hover/ARIA improvements.
   - Run browser-based smoke checks to confirm responsiveness and accessibility
     tooling catch no regressions.
3. **Iteration 3 – Surface styling & tokens (Days 5-6)**
   - Update cards, buttons, and result grids with new gradients, shadows, and
     focus-visible treatments.
   - Exercise regression scripts on small-screen breakpoints.
4. **Iteration 4 – Documentation & follow-up backlog (Day 7)**
   - Update requirements, plan documents, and capture future UI backlog items.
   - Prepare before/after visuals for stakeholder review.

## Acceptance Criteria
- Hero area contains eyebrow label, headline, and three localised highlight
  cards describing guided inputs, localisation previews, and the Sankey view.
- Sankey diagram renders with distinct node/link colours, displays a legend, and
  maintains accessible hover/ARIA metadata even when no data is present.
- Summary cards, detail cards, and action buttons adopt refreshed design tokens
  with focus-visible styling and maintain readability on 320 px wide screens.
- Documentation references the new visual communication requirement and outlines
  at least three future UI enhancements for subsequent sprints.

## Dependencies & Risks
- Localisation updates may require coordination with translators for new highlight
  copy and legend descriptions.
- Plotly configuration changes must stay compatible with backend data shapes to
  avoid runtime chart errors.
- Accessibility tooling (e.g., axe) should be rerun after visual updates to guard
  against colour contrast regressions.

## Out of Scope
- Introducing a dark theme or advanced animation sequencing (tracked for future
  sprints).
- Modifying the tax calculation logic or API payload formats.
- Adding new income or deduction categories beyond existing configuration data.

## References
1. GreekTax Requirements – non-functional visual communication guidance.【F:Requirements.md†L96-L111】
2. Front-end localisation catalogue for hero and Sankey copy.【F:src/frontend/assets/scripts/main.js†L20-L118】【F:src/frontend/assets/scripts/main.js†L241-L339】
3. Current Sankey rendering implementation for refinement baseline.【F:src/frontend/assets/scripts/main.js†L2079-L2350】
