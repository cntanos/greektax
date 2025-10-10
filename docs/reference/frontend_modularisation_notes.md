# Front-end Modularisation Notes

## Goals

- Decompose the monolithic `src/frontend/assets/scripts/main.js` into cohesive modules aligned with calculator features.
- Establish a lightweight build and bundling pipeline that supports ES module syntax, localisation embedding, and shared state management.
- Improve testability and accessibility by isolating DOM manipulation and data formatting concerns.

## Proposed module boundaries

1. **`api/client.ts`** – Fetch wrapper handling configuration requests, calculation submissions, and error translation. Exposes typed request/response helpers generated from OpenAPI definitions.
2. **`state/store.ts`** – Central store (e.g., Zustand or vanilla reactive store) responsible for current form data, derived totals, and persistence to `localStorage` with schema validation.
3. **`ui/forms/` components** – Small modules per income category that render inputs, subscribe to store slices, and emit events. Each component owns its validation messages and accessibility labels.
4. **`ui/summary/`** – Formatting utilities and rendering logic for the results summary, including chart adapters.
5. **`i18n/index.ts`** – Loader consuming generated translation bundles (from the embed script replacement), exposing hooks/utilities for runtime locale switching.
6. **`bootstrap.ts`** – Entry point wiring modules together, initialising locale, attaching event listeners, and kicking off the first calculation.

## Supporting infrastructure

- Replace the ad-hoc translation embed with a build step that consumes JSON catalogues, validates key parity, and emits typed modules consumed by `i18n/index.ts`.
- Introduce Vite (or similar) configuration enabling TypeScript, PostCSS, and static asset copying. Output to `dist/` with hashed filenames.
- Add ESLint/Prettier configuration aligned with the repository’s Python linting philosophy to maintain consistent formatting.
- Define contract tests using Vitest for store logic and DOM testing library for component behaviour.

## Migration steps

1. **Baseline extraction** – Split `main.js` into `bootstrap.ts` and `api/client.ts` while keeping legacy global functions operational.
2. **Incremental componentisation** – Port each form section to modules, adding tests before removing legacy code. Maintain exported APIs for existing scripts until parity achieved.
3. **Enable build pipeline** – Introduce Vite config and adjust CI to run lint/test/build tasks; update deployment scripts to serve bundled assets.
4. **Retire legacy bundle** – Once modules ship, remove `translations.generated.js` in favour of typed imports, and delete unused global helpers.

## Open questions

- Should the front-end adopt a micro-library (e.g., Preact) for templating, or remain vanilla with template literals?
- How to expose runtime feature flags (e.g., new schema toggles) to the UI without coupling to build-time constants?
- What metrics (bundle size, FCP) will define success post-modularisation?
