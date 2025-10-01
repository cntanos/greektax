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
pip install -e .[dev]
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

## Configuring the API endpoint

The front-end maintains an ordered list of candidate API base URLs and falls
back automatically when a host does not respond (for example, when a CMS proxy
is unavailable or a remote API blocks cross-origin requests). By default the
candidates are:

1. Any explicitly configured override (see below).
2. `/api/v1`, which keeps requests on the same origin as the static assets.
3. `https://cntanos.pythonanywhere.com/api/v1`.

When embedding the calculator in a CMS or iframe, you can override the first
candidate without rebuilding the assets. The lookup order for explicit
overrides is:

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
4. URL query parameters appended to the calculator entrypoint:
   - `?greektax-api-base=…`
   - `?greektax_api_base=…`
   - `?apiBase=…`
   - `?api_base=…`

The chosen value is normalised to remove trailing slashes before being used in
requests.

If an override is unavailable (for example, a proxy path returns `404` or a
remote API blocks the iframe origin with CORS), the next candidate in the list
is attempted automatically. Successful responses pin the working base URL for
the remainder of the session.

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

## License

GreekTax is released under the [GNU General Public License v3.0](LICENSE).

&copy; 2024 Christos Ntanos for CogniSys. Released under the GNU GPL v3.
