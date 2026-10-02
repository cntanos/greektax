# GreekTax

GreekTax is a bilingual web application that helps taxpayers in Greece estimate annual obligations across employment, freelance, rental, agricultural, and related income categories.

It is a static site: every calculation runs in the browser and no input leaves the device. The Python package in `src/greektax/` is the reference implementation of the calculation engine and the source of the year configuration; it is used to build and test the site, not to serve it.

> **Disclaimer**: GreekTax is not an official government tool. Results are informational only; consult a professional accountant for formal filings.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pip install -e .
```

Serve the site locally (any static file server works; opening `index.html` from disk does not, because it uses JavaScript modules):

```bash
python -m http.server 8000 --bind 127.0.0.1 --directory src/frontend
```

Run the core checks before submitting changes:

```bash
python scripts/quality.py
pytest
npm run test:frontend
python scripts/validate_config.py
```

## Canonical Documentation

- **Architecture**: [`docs/architecture.md`](docs/architecture.md)
- **i18n workflow**: [`docs/i18n.md`](docs/i18n.md)
- **Performance process**: [`docs/performance_baseline.md`](docs/performance_baseline.md)
- **Operational index**: [`docs/operations.md`](docs/operations.md)
- **Contributing guide**: [`docs/contributing.md`](docs/contributing.md)
- **Requirements**: [`Requirements.md`](Requirements.md)
- **Tax rules and sources (2025-2026)**: [`docs/reference/tax_rules_2025_2026.md`](docs/reference/tax_rules_2025_2026.md)
- **Changelog**: [`CHANGELOG.md`](CHANGELOG.md)

## Notes for contributors

- After changing a year file, translations or the version, run `python scripts/build_client_config.py` and `python scripts/generate_parity_fixtures.py` (see [`docs/operations.md`](docs/operations.md)); `pytest` fails while either output is stale.
- Dependency metadata is managed in `pyproject.toml`. Regenerate derived requirements files with `python scripts/sync_requirements.py`.
- If UI translation strings change, run `python scripts/embed_translations.py` and commit the generated bundle.
- Keep README updates minimal: point to canonical docs instead of duplicating procedures.
