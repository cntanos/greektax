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

Run the placeholder tests to validate the scaffold:

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

## Tax Logic & Recent Updates

- Charitable donations now yield a direct tax credit instead of reducing taxable
  income. This aligns the calculator with the latest deduction engine updates
  and validation tests.
- As of the 2024 filing year, most individual scenarios no longer include a
  trade fee by default. The simulator only surfaces the fee when a filing status
  or profession explicitly requires it.

### Highlights from the Last 15 Commits

- Expanded automated coverage for new tax credit and trade fee branches to keep
  regression risk low (802148a).
- Improved inline guidance and bilingual copy across form steps to clarify data
  entry expectations (1ac622b).
- Sharpened employment and pension toggle wording for clearer user decisions
  (e49d997).
- Introduced an employment income mode toggle so contributors can model payroll
  and pension flows separately (18944c7).
- Reworked the deduction engine to support credit-based relief and consistent
  calculations across income types (892a1af).
- Delivered responsive Sankey sizing improvements so the allocation chart fits
  small screens without clipping (7bc8935).
- Patched Sankey overflow bugs that previously hid labels on dense datasets
  (c02dc13).
- Refined investment detail styling with better numeric emphasis for comparison
  scanning (6543fce).
- Ensured the results section is visible before the Sankey renders to avoid
  layout shifts during loading (182b234).
- Added a built-in fallback when `Flask-Cors` is unavailable to keep the API
  responsive in minimal deployments (a5c9f61).
- Streamlined API base detection logic so hosted deployments default to the
  remote endpoint when appropriate (bbf5e84).
- Simplified client-side base URL selection to reduce maintenance overhead
  (7423a7a).
- Enabled CORS across API endpoints, unblocking integrations with embedded
  front-ends (56ccfd9).
- Defaulted production builds to the same-origin API base for improved security
  defaults (c621d8c).
- Added explicit overrides for embedded deployments so CMS integrations can
  point to bespoke API hosts (be1da47).

## Configuring the API endpoint

The front-end automatically selects which API base URL to use:

- `/api/v1` for same-origin deployments (including loopback, private network,
  or custom domains).
- `https://cntanos.pythonanywhere.com/api/v1` when hosted directly from the
  PythonAnywhere environment.

When embedding the calculator in a CMS or iframe, you can override the detected
endpoint without rebuilding the assets. The lookup order is:

1. A global variable defined before `assets/scripts/main.js` runs:
   ```html
   <script>
     window.__GREEKTAX_API_BASE__ = "https://example.com/custom/api";
   </script>
   ```
2. A `<meta>` tag in the document head:
   ```html
   <meta name="greektax:api-base" content="https://example.com/custom/api" />
   ```
3. A `data-api-base` attribute on the loader script tag:
   ```html
   <script src="./assets/scripts/main.js" data-api-base="https://example.com/custom/api"></script>
   ```

The chosen value is normalised to remove trailing slashes before being used in
requests.

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

The canonical version is declared once in [`pyproject.toml`](pyproject.toml) and
is surfaced automatically via the `/api/v1/config/meta` endpoint and the UI
footer. Bump the value there to propagate the new release identifier
everywhere.

## License

GreekTax is released under the [GNU General Public License v3.0](LICENSE).

&copy; 2025 Christos Ntanos for CogniSys. Released under the GNU GPL v3 License.
