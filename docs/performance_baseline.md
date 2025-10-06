# Performance & Accessibility Baseline

Sprint 18 introduces lightweight tooling for tracking calculation timings,
front-end bundle sizes, and accessibility metadata so the team can monitor
optimisation work over time. The `scripts/performance_snapshot.py` helper wraps
the back-end calculation service, inspects critical static assets, and scans the
HTML shell for ARIA usage. Use this workflow alongside localisation and UI
reviews so that catalogue or styling changes are reflected in the historical
baseline.

## Running the snapshot

```bash
# Default run with 75 iterations of the calculation engine
scripts/performance_snapshot.py

# Override the number of repetitions for slower environments
GREEKTAX_PROFILE_ITERATIONS=150 scripts/performance_snapshot.py
```

Sample output captured after the sprint improvements:

```
{
  "accessibility_snapshot": {
    "nodes_with_aria": 17,
    "roles": ["group", "img", "list", "listitem"]
  },
  "backend": {
    "average_ms": 0.1219,
    "iterations": 75,
    "max_ms": 0.8269,
    "min_ms": 0.1011,
    "total_ms": 9.1437
  },
  "frontend_assets_bytes": {
    "src/frontend/assets/scripts/main.js": 101618,
    "src/frontend/assets/styles/main.css": 19676
  }
}
```

The calculation timings rely on the profiling hooks in
`greektax/backend/app/services/calculation_service.py`. Setting the environment
variable `GREEKTAX_PROFILE_CALCULATIONS=true` prints per-section timings for
ad-hoc investigations while keeping the API contract unchanged. The snapshot now
reports minimum and maximum iteration durations to surface jitter alongside the
average and cumulative timings. After significant localisation batches or UI
refresh work, coordinate reruns with the
[`docs/i18n.md`](i18n.md) and [`docs/ui_improvement_plan.md`](ui_improvement_plan.md)
workflows so bundle and render changes stay measurable.

## Related Workflows

- [`docs/i18n.md`](i18n.md) – localisation guidance for catalogue updates that
  often precede performance sampling.
- [`docs/ui_improvement_plan.md`](ui_improvement_plan.md) – UI polish checklist
  that may influence asset payloads and accessibility metrics captured here.
