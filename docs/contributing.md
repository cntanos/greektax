# Contributing Guide

This guide complements the quick-start and checklist material in the project
README.

## Repository Hygiene

Keep files close to the layer they serve so maintenance and packaging stay
predictable.

### Root directory

Keep only repository-wide files at the root:

- project metadata and dependency manifests (for example `pyproject.toml`,
  generated `requirements*.txt`)
- legal/project-level references (`LICENSE`, `README.md`, `Requirements.md`)
- automation entry points (`scripts/`, CI/editor configuration)

Avoid adding feature code, one-off experiment files, or deployment-specific
copies in root.

### `src/`

`src/` should contain importable application code and runtime assets only.

- Python packages under `src/greektax/` (backend app, configuration, shared
  translations)
- static frontend bundle assets under `src/frontend/`
- production entrypoints that are executed by hosts (for example
  `src/greektax/backend/passenger_wsgi.py`)

Do not add placeholder package markers or scratch modules that are not imported
by runtime code, tests, or packaging configuration.

### `docs/`

Place contributor-facing references in `docs/`:

- architecture and API contracts
- operational runbooks and manual test guides
- roadmap/planning notes

If a file is an example/template, label it clearly in the filename or heading
(e.g. `*.example.*`) and explain where it is used.
