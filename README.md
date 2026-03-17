# GreekTax

GreekTax is a bilingual web application that helps taxpayers in Greece estimate annual obligations across employment, freelance, rental, agricultural, and related income categories.

> **Disclaimer**: GreekTax is not an official government tool. Results are informational only; consult a professional accountant for formal filings.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pip install -e .
```

Run the core checks before submitting changes:

```bash
pytest
ruff check src tests
mypy src
python scripts/validate_config.py
```

## Canonical Documentation

- **Architecture**: [`docs/architecture.md`](docs/architecture.md)
- **i18n workflow**: [`docs/i18n.md`](docs/i18n.md)
- **Performance process**: [`docs/performance_baseline.md`](docs/performance_baseline.md)
- **Operational index**: [`docs/operations.md`](docs/operations.md)
- **Contributing guide**: [`docs/contributing.md`](docs/contributing.md)
- **Requirements**: [`Requirements.md`](Requirements.md)

## Notes for contributors

- Dependency metadata is managed in `pyproject.toml`. Regenerate derived requirements files with `python scripts/sync_requirements.py`.
- If UI translation strings change, run `python scripts/embed_translations.py` and commit the generated bundle.
- Keep README updates minimal: point to canonical docs instead of duplicating procedures.
