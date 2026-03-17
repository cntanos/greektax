# Operational Workflows Index

Use this page as a routing index. Detailed procedures live in their canonical documents to avoid duplication.

## Workflow pointers

- **Localisation updates** → [`docs/i18n.md`](i18n.md)
- **Performance baselines** → [`docs/performance_baseline.md`](performance_baseline.md)
- **Architecture and system boundaries** → [`docs/architecture.md`](architecture.md)
- **UI review loops** → [`docs/ui_improvement_plan.md`](ui_improvement_plan.md)
- **Contribution process** → [`docs/contributing.md`](contributing.md)

## Year configuration refreshes

When introducing or updating filing years in `src/greektax/backend/config/data/*.yaml`:

1. Update the year YAML file.
2. Run `python scripts/validate_config.py`.
3. Run `pytest`.
4. Document any user-facing copy impacts in the i18n workflow doc.

For localisation details, use [`docs/i18n.md`](i18n.md) directly.
