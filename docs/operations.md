# Operational Workflows Index

Centralise the day-to-day workflows that keep GreekTax healthy. Each guide
provides detailed steps, but this index outlines when to use them and how they
connect so contributors can plan multi-disciplinary changes without surprises.

## Localisation Updates
- **When to use**: Any time copy changes are required or new locales are
  introduced.
- **Key actions**: Update the JSON catalogues, rebuild the embedded bundle, and
  verify API responses and UI previews.
- **Stay aligned**: Large catalogue updates can impact render timings and
  bundle sizes—schedule a follow-up performance snapshot to capture the delta.
- **Full workflow**: [`docs/i18n.md`](i18n.md)

## Performance Baselines
- **When to use**: After feature work that changes calculations, asset bundles,
  or localisation payloads.
- **Key actions**: Run `scripts/performance_snapshot.py`, compare trends, and
  update tracking dashboards as needed.
- **Stay aligned**: Coordinate with the localisation workflow when large copy
  batches land and with UI reviews when visual refinements grow asset payloads.
- **Full workflow**: [`docs/performance_baseline.md`](performance_baseline.md)

## UI Review Loops
- **When to use**: During visual refresh sprints or any change that adjusts the
  presentation layer.
- **Key actions**: Apply design tokens, validate accessibility, and capture
  review notes for future iterations.
- **Stay aligned**: Account for new localisation strings in layouts and rerun
  performance snapshots if asset budgets shift.
- **Full workflow**: [`docs/ui_improvement_plan.md`](ui_improvement_plan.md)

## Year configuration refreshes
- **When to use**: At the start of a new filing year or when the Ministry of
  Finance publishes updated brackets, deductions, or contribution schedules.
- **Key actions**: Duplicate the most recent YAML file under
  `src/greektax/backend/config/data`, adjust the economic parameters, and run
  `python scripts/validate_config.py` to ensure the schema stays compliant.
- **Stay aligned**: Follow up with `pytest` to exercise the calculator against
  the refreshed dataset and update the public requirements summary so guidance
  in [`Requirements.md`](../Requirements.md) stays accurate.
- **Full workflow**: Coordinate with the localisation guide in
  [`docs/i18n.md`](i18n.md) when new deductions introduce user-facing copy or
  metadata that the UI must surface.
