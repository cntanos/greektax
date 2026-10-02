# GreekTax review guidelines

GreekTax is a Greek tax calculator. It is a static site in
`src/frontend/`: every calculation runs in the browser with the engine in
`src/frontend/assets/scripts/engine/`, and no input leaves the device.
The Python package in `src/greektax/` is not deployed; it holds the year
configuration and the reference engine that the JavaScript engine must
match exactly. There is no server, no auth, no PII storage, no database.
The single production deployment is `cognisys.gr`, served via cPanel.

This file is loaded at the start of every PR review. Use it to
prioritise findings.

## What to focus on

### Correctness

- Pydantic models in `src/greektax/backend/app/models/` reject extra
  fields by convention (`model_config = ConfigDict(extra="forbid")`), and
  `engine/request.js` mirrors them. New optional fields must default
  cleanly in both.
- Any calculation change that is not purely YAML must be made in both
  engines (`src/greektax/backend/app/services/` and
  `src/frontend/assets/scripts/engine/`). `tests/frontend/engineParity.test.js`
  requires exact agreement on every case in `tests/data/parity/`; flag a PR
  that regenerates those fixtures without explaining the changed
  expectations.
- `src/frontend/assets/scripts/ui/app.js` is a ~5800-line module.
  Every identifier it references must be declared, imported, or a
  browser/standard global. The refactor in PR #221 dropped eleven
  declarations that surfaced as runtime `ReferenceError`s only after
  deployment. Flag any new bare-identifier reference (read, write,
  update, member access) that lacks a declaration.
- Tax brackets and rate tables live in
  `src/greektax/backend/config/data/*.yaml`. Changes there must come
  with a `python scripts/validate_config.py` check and a source for each
  changed figure; flag PRs that modify a year file without either.
  `docs/reference/tax_rules_2025_2026.md` records the current figures
  and their sources.

### Security

- There is no backend. A change that sends user input off the device
  (for example a `fetch`, a beacon or analytics) is a privacy
  regression: the page promises that entries never leave the device.
- localStorage persistence is **opt-in** (PR #241). Form fields that
  need to skip persistence must carry `data-no-persist`. Persisting
  financial data without honouring `calculatorPersistenceOptIn` is a
  regression.
- XSS: engine results and user content reach the DOM via `textContent`.
  `innerHTML` is reserved for static-template clearing. Any new
  `innerHTML = <interpolated>` is a bug — call it out.
- New third-party (non-GitHub) workflow actions must be pinned by SHA;
  an unpinned tag is a security finding.

### Tests

- Frontend tests: `tests/frontend/*.test.js`, run via
  `npm run test:frontend` (which globs `tests/frontend/*.test.js`).
  JSDOM- and acorn-dependent tests skip gracefully when those optional
  dev deps are not installed.
- Python tests (reference engine, configuration, build scripts):
  `tests/{unit,config}/`, run via `pytest`.
- `tests/frontend/fileSizeGuardrails.test.js` caps
  `src/frontend/assets/scripts/ui/app.js` at 5900 lines. If a change
  pushes it over, either trim or justify a budget bump in the PR.
- New conditional branches in either codebase should arrive with a
  matching test case. Coverage gaps in changed code are worth flagging.

## What to skip

- Style nits already enforced by `ruff` (lint/format) and `mypy`
  (typing). The CI workflow runs both; spending review effort on
  selectors they already cover is noise.
- Hypothetical generality. This is a single-deployment project;
  suggestions framed as "what if someone forks this for a different
  host" are not actionable. Frame findings in terms of the existing
  deployment.
- Translation phrasing. Both EL and EN translations are maintained by
  the project owner; flag *missing keys* or `t(key)` calls that
  resolve to a literal key (a deployment cache issue we've hit before
  — see PR #242), not wording choices.

## Conventions worth knowing

- Translation files: `src/greektax/translations/{en,el}.json`. After
  edits, run `python scripts/embed_translations.py` to regenerate
  `src/frontend/assets/scripts/translations.generated.js`; otherwise
  the deployed UI shows literal keys.
- Deployed-static-asset cache busting: `scripts/configure_frontend.py`
  appends `?v=<hash>` to every relative JS import (including dynamic
  `import()`) and every `<script src="./assets/scripts/*.js">` tag at
  deploy time (PR #242). New `<script>` tags or module imports that
  bypass this mechanism will hit stale caches.
- Generated files: after editing a year file, translations or the
  version, run `python scripts/build_client_config.py` and
  `python scripts/generate_parity_fixtures.py`; `pytest` fails while
  their outputs are stale.

## Output format

Two channels:

1. **One top-level summary comment** posted via `gh pr comment`. Use
   this for the holistic read of the PR — what it does, the main
   findings, and a verdict. Format:

   - One short paragraph describing what the PR does.
   - A short bulleted list of material findings, each prefixed with
     `[bug]` / `[security]` / `[perf]` / `[test]` / `[nit]`. Omit
     the list if there are no findings worth surfacing.
   - A final line beginning with `Verdict:` followed by one of
     "Ready", "Address findings then merge", or "Needs rework".

2. **Inline review comments** anchored to specific file:line locations
   via `mcp__github_inline_comment__create_inline_comment` (with
   `confirmed: true`). Use these only when a finding is genuinely
   anchored to one location and reading it in context helps. Keep
   each one 1-3 sentences with the same tag prefix.

Tag legend:

- `[bug]` — incorrect behaviour or regression
- `[security]` — security-relevant change worth attention
- `[perf]` — performance concern with measurable impact
- `[test]` — missing or weak test coverage
- `[nit]` — minor suggestion, use sparingly

If nothing in the diff warrants attention, post a summary that says
so (one paragraph + `Verdict: Ready`) and skip the inline channel.
Silence on both channels is also acceptable, but a one-line "Ready"
is clearer for the reader.
