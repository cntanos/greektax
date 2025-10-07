# GreekTax

GreekTax is an unofficial, bilingual web application that helps taxpayers in
Greece estimate their annual obligations across employment, freelance, rental,
and related income categories. The project emphasises transparency,
maintainability, and ease of deployment through a modern Python stack.

> **Disclaimer**: GreekTax is not an official government tool. Results are for
> informational purposes only; consult a professional accountant for formal
> filings.

## Documentation Outline

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Architecture & Planning References](#architecture--planning-references)
4. [Contributor Checklist](#contributor-checklist)
5. [Versioning & Release Guidance](#versioning--release-guidance)

## Overview

- **Architecture**: Flask API under `src/greektax/backend` and a static
  front-end under `src/frontend`, both sharing localisation catalogues and
  configuration assets.
- **Data-driven tax logic**: Yearly YAML data files under
  `src/greektax/backend/config/data` allow updates without touching Python code.
- **Translations**: Shared bilingual catalogues power API responses and the UI,
  with tooling to embed the latest strings in the static bundle.
- **Testing focus**: Unit, integration, and regression coverage keeps complex
  business rules verifiable as regulations change.

Repository layout:

```
├── docs/                   # Architecture, roadmap, and localisation references
├── src/
│   ├── greektax/backend/   # Flask API scaffolding and configuration
│   └── frontend/           # Static assets and UI placeholders
├── tests/                  # Unit, integration, and regression coverage
├── pyproject.toml          # Project metadata and tooling configuration
└── Requirements.md         # Functional and non-functional requirements
```

## Quick Start

### 1. Set up a local environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pip install -e .
```

Optional: install Node.js if you plan to experiment with future front-end
tooling.

### 2. Run verification commands

Use the automated checks to keep the scaffold healthy:

```bash
pytest                         # Execute unit and integration tests
ruff check src tests           # Lint Python code
mypy src                       # Static type checks
python -m greektax.backend.config.validator  # Validate YAML configuration
```

### 3. Refresh localisation bundles when strings change

```bash
python scripts/embed_translations.py
```

The script rebuilds
`src/frontend/assets/scripts/translations.generated.js`. Commit the regenerated
file so static deployments remain in sync with the canonical catalogues. See
[`docs/i18n.md`](docs/i18n.md) for end-to-end localisation guidance.

### 4. Configure cross-origin access

The API enforces an allow-list for browser origins via the
`GREEKTAX_ALLOWED_ORIGINS` environment variable. Set it to a comma-separated
list before running the server so front-end deployments can call the API:

```bash
export GREEKTAX_ALLOWED_ORIGINS="http://localhost:5173"
flask --app greektax.backend.app:create_app run
```

- **Staging**: include the staging UI origin alongside any developer domains,
  e.g. `GREEKTAX_ALLOWED_ORIGINS="http://localhost:5173,https://staging.tax.example"`.
- **Production**: restrict the list to the public domain that serves the UI,
  e.g. `GREEKTAX_ALLOWED_ORIGINS="https://app.tax.example"`.

If the variable is unset or empty, cross-origin requests are rejected for both
the Flask-Cors integration and the built-in fallback.

## Development Environment

Use the [Operational Workflows Index](docs/operations.md) as the entry point for
recurring contributor tasks. It summarises localisation updates, performance
baseline captures, and UI review loops with links to the detailed guides.

## Architecture & Planning References

- [`docs/architecture.md`](docs/architecture.md) — module boundaries, deployment
  model, and maintenance workflows.
- [`docs/project_plan.md`](docs/project_plan.md) — roadmap, sprint history, and
  upcoming milestones.
- [`docs/operations.md`](docs/operations.md) — index of localisation,
  performance, and UI review workflows.
- [`Requirements.md`](Requirements.md) — product requirements and acceptance
  criteria.

## Contributor Checklist

Before opening a pull request:

- **Prepare the environment**
  - Create/refresh the virtual environment and install development dependencies.
  - Activate recommended editor settings (see `.vscode/` for VS Code defaults).
- **Update artefacts**
  - Run `pytest`, `ruff check src tests`, and `mypy src`; address failures.
  - Execute `python -m greektax.backend.config.validator` to catch configuration
    regressions.
  - Run `python scripts/embed_translations.py` after localisation updates and
    commit the generated assets.
- **Documentation**
  - Sync relevant references in `docs/` if behaviour, endpoints, or workflows
    change.
  - Note roadmap impacts in [`docs/project_plan.md`](docs/project_plan.md).

## Versioning & Release Guidance

- Project versioning is managed via the `version` field in
  [`pyproject.toml`](pyproject.toml); update it when preparing a release.
- Tag repository releases with the matching version number and summarise
  highlights in the project plan.
- Keep generated artefacts and localisation bundles in sync with the declared
  version so published packages reflect the documented capabilities.
