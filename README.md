# GreekTax

GreekTax is a bilingual web application that helps taxpayers in
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

### 4a. Configure PythonAnywhere production settings

PythonAnywhere's free tier does not expose an environment-variable UI, so set
`GREEKTAX_ALLOWED_ORIGINS` inside the WSGI entrypoint instead. Replace
`/var/www/cntanos_pythonanywhere_com_wsgi.py` with the snippet below (adjust the
username if you fork the project):

```python
import os
import sys
from pathlib import Path

os.environ.setdefault("GREEKTAX_ALLOWED_ORIGINS", "https://www.cognisys.gr")

project_root = Path("/home/cntanos/greektax")
sys.path.insert(0, str(project_root / "src"))

from greektax.backend.app import create_app  # noqa: E402

application = create_app()
```

- `os.environ.setdefault` injects the production allow-list so only your public
  UI domain can call the API. Update the URL if the front-end moves.
- The `sys.path` insertion ensures the WSGI loader can import the Flask app.
- After saving the file, click **Reload** in the PythonAnywhere Web dashboard to
  apply the changes.

### 5. Point static deployments at the correct API base URL

The front-end script now detects the API endpoint from the hosting environment
without requiring a custom build. Hosting providers can inject
`window.GREEKTAX_API_BASE` or a `<meta data-api-base>` element before
`assets/scripts/main.js` loads.

- **cPanel or basic HTML editors**: open the page template and add the snippet
  below inside `<head>`:

  ```html
  <meta data-api-base="https://api.tax.example/api/v1">
  <script defer src="/assets/scripts/main.js"></script>
  ```

- **Static site generators / template includes**: expose an include or partial
  that writes the `<meta data-api-base>` tag or an inline script assigning
  `window.GREEKTAX_API_BASE`. Pull the base URL from the deployment config so
  each environment (preview, staging, production) renders the correct value.

- **Small config JSON**: serve a lightweight `greektax.config.json` alongside
  the static bundle and hydrate the global before the main script executes:

  ```html
  <script type="module">
    try {
      const response = await fetch('/greektax.config.json', { cache: 'no-store' });
      if (response.ok) {
        const config = await response.json();
        if (config?.apiBase) {
          window.GREEKTAX_API_BASE = config.apiBase;
        }
      }
    } catch (error) {
      console.warn('Unable to load greektax.config.json; falling back to defaults.', error);
    }
  </script>
  <script defer src="/assets/scripts/main.js"></script>
  ```

  The JSON file can be generated during deployment (e.g. via CI secrets) to
  avoid manual edits to the bundled assets.

#### 5a. cPanel deployment expectations

- The repository's `.cpanel.yml` assumes WordPress rewrites
  `https://www.cognisys.gr/greektax/` into the document root at
  `~/public_html/wp-content/uploads/greektax`. Keep that rewrite rule in place or
  adjust the `DEPLOYPATH` export in the script to match your hosting layout.
- Leave the deployed directory world-readable. Earlier revisions attempted to
  remove world permissions and produced 403 responses for CSS/JS assets; the
  current script intentionally omits any `chmod` step so Apache/Nginx can serve
  the files.

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
