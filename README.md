# GreekTax

GreekTax is an unofficial, bilingual web application designed to help taxpayers
in Greece estimate their annual obligations across employment, freelance,
rental, and other income categories. The project emphasises transparency,
maintainability, and ease of deployment by using widely adopted web
technologies.

> **Disclaimer**: GreekTax is not an official government tool. Results are for
> informational purposes only; consult a professional accountant for formal
> filings.

## Repository Layout

```
├── docs/                   # Project plan, architecture notes, and sprint logs
├── src/
│   ├── greektax/backend/   # Flask-based API scaffolding and configuration
│   └── frontend/           # Static assets and UI placeholders
├── tests/                  # Unit, integration, and future end-to-end tests
├── pyproject.toml          # Project metadata and tooling configuration
└── Requirements.md         # Detailed functional and non-functional requirements
```

Refer to [`docs/project_plan.md`](docs/project_plan.md) for epics, sprint
objectives, and delivery roadmap updates.

## Architecture Overview

GreekTax is split between a Flask API (`src/greektax/backend`) and a static
front-end (`src/frontend`). The back-end publishes calculation, configuration,
and localisation endpoints consumed by the UI, while the front-end embeds the
shared translation catalogue and issues JSON requests against the API. Yearly
tax rules are managed as YAML data files under
`src/greektax/backend/config/data`, letting maintainers add new filing years
without touching Python code. See [`docs/architecture.md`](docs/architecture.md)
for a detailed walkthrough of the module boundaries, deployment model, and
maintenance workflows.

## Development Environment

### Prerequisites
- Python 3.10+
- Node.js (optional, for future front-end tooling)
- Recommended editor: Visual Studio Code with the workspace configuration in
  [`.vscode/`](.vscode/)

### Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pip install -e .
```

### Testing & Quality

Run the automated checks to keep the scaffold healthy:

```bash
pytest
```

Validate configuration files to surface contributor-facing alerts:

```bash
python -m greektax.backend.config.validator
```

### Refreshing front-end translations

Whenever you update the shared catalogues in `src/greektax/translations`,
regenerate the embedded front-end bundle so the static UI picks up the changes:

```bash
python scripts/embed_translations.py
```

This script reads the canonical JSON resources and emits
`src/frontend/assets/scripts/translations.generated.js`, which the browser loads
before the main application script. The generated file should be committed so
static deployments remain in sync with the latest catalogue content.

Refer to [`docs/i18n.md`](docs/i18n.md) for the full localisation workflow,
including how to add new strings or support additional languages.

Additional tooling configured for future sprints:

- `ruff` for linting (`ruff check src tests`)
- `mypy` for static type checks (`mypy src`)

### Performance Snapshot

Capture a lightweight performance and accessibility baseline with the
instrumented helper:

```bash
python scripts/performance_snapshot.py
```

The report logs backend calculation timings (including minimum, maximum, and
average durations), bundle sizes for the key front-end assets, and ARIA usage in
the HTML shell. See [`docs/performance_baseline.md`](docs/performance_baseline.md)
for guidance on interpreting the output.

## Current Capabilities

- **Comprehensive calculation engine** – The Flask back end validates incoming
  payloads, normalises employment and freelance entries, and produces bilingual
  summaries for income, deductions, and optional obligations such as ENFIA and
  luxury levies.【F:src/greektax/backend/app/services/calculation_service.py†L1-L240】
- **Public API contract** – Versioned endpoints expose calculation, metadata,
  and localisation resources so the static front end and external clients can
  consume the same business rules.【F:docs/api_contract.md†L1-L226】
- **Translation pipeline** – Localised strings live in shared catalogues that
  power both the Flask responses and the static UI. The `embed_translations.py`
  script regenerates the front-end bundle to keep the two layers in sync.【F:scripts/embed_translations.py†L1-L109】
- **Static front-end shell** – A responsive calculator front end renders
  interactive forms, Sankey visualisations, and summaries with language and
  theme switching powered by the embedded translations.【F:src/frontend/index.html†L1-L560】【F:src/frontend/assets/scripts/main.js†L20-L2549】

## Tax Logic & Recent Updates

- Charitable donations yield direct credits within the deduction engine while
  maintaining audit-friendly detail rows in the response payload.【F:src/greektax/backend/app/services/calculation_service.py†L904-L1020】
- Trade fee handling reflects the latest filing guidance, only adding the charge
  for professions or start years that require it.【F:src/greektax/backend/app/services/calculation_service.py†L702-L776】

## Configuring the API endpoint

The front-end reads a single `API_BASE` constant near the top of
`src/frontend/assets/scripts/main.js`. It defaults to the hosted
`https://cntanos.pythonanywhere.com/api/v1` service so static deployments work
out of the box. For local development or self-hosted installs, switch the
commented line to `LOCAL_API_BASE` before building or serving the assets from the
Flask application. When embedding the calculator in a CMS, serve the static
bundle from the same origin as your API or fork the repository to bake in the
desired endpoint.

## Brand & Media Assets

Binary media files are intentionally not stored in this repository. When UI work
needs CogniSys-branded imagery or logos, reference the assets hosted on
https://www.cognisys.gr/ or reproduce them with CSS/SVG so pull requests remain
text-only.

## Roadmap

Development follows iterative sprints grouped by epics. Each sprint update will
be documented in the project plan. Key focus areas for upcoming sprints include:

1. Completing year-based configuration schemas and validation.
2. Building the modular tax calculation engine with comprehensive tests.
3. Delivering a responsive, bilingual user interface integrated with the API.

Contributions are welcome via pull requests. Please consult the project plan and
TODO markers across the codebase for the current priorities.

## Versioning

GreekTax tracks releases with the semantic pattern **R.X.Y**:

- **R** – release cycle number signifying major public milestones. This only
  increments when a full release is declared.
- **X** – sprint-level increments that bundle new features or significant UI
  updates. Increase this when a sprint concludes with a packaged deliverable.
- **Y** – fix iterations for hot-fixes or polish delivered within a sprint.
  Increment this for follow-up patches within the same sprint.

The current milestone is **R.5.0** (version `0.5.0` in `pyproject.toml`),
reflecting the fifth major sprint within the initial release cycle.

The canonical version is declared once in [`pyproject.toml`](pyproject.toml) and
is surfaced automatically via the `/api/v1/config/meta` endpoint and the UI
footer. Bump the value there to propagate the new release identifier
everywhere.

## License

GreekTax is released under the [GNU General Public License v3.0](LICENSE).

&copy; 2025 Christos Ntanos for CogniSys. Released under the GNU GPL v3 License.
