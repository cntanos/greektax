# Documentation Style & Voice Guide

## Purpose
Provide a shared reference for contributors updating README.md, Requirements.md, and files in docs/ so that future documentation changes follow consistent structure, tone, and referencing.

## Headings
- Use sentence case for section headings (capitalise only the first word and proper nouns) to match the current documentation refresh.
- Keep top-level documents under 3 heading levels where possible; prefer concise subsections over deeply nested hierarchies.
- Begin documents with an H1 that states the artifact’s role (e.g., “Documentation audit” or “Internationalisation workflow”).

## Voice & Tone
- Write in an instructive, confident voice that focuses on practical steps and rationale.
- Prefer present tense and direct language (e.g., “Run the script” instead of “You should run the script”).
- When describing future work, indicate ownership and expected outcome to keep backlog notes actionable.

## Localisation Callouts
- Note when instructions differ for Greek versus English audiences or when bilingual assets must be updated; use inline callouts like “(update both `en` and `el` catalogues)” rather than lengthy prose.
- Reference localisation workflows via docs/i18n.md unless new behaviour is being introduced; avoid re-explaining the pipeline in multiple places.
- Highlight UI copy changes with locale tags or key names so translators can find the relevant strings quickly.

## Command & Code Formatting
- Use fenced code blocks with an explicit language identifier (```` ```bash ```` for shell commands, ```` ```python ```` for Python snippets).
- Show full commands, including `python` or environment variables, to prevent ambiguity across operating systems.
- When commands span multiple steps, keep them in execution order and avoid inline ellipses that obscure required flags.

## Citations & References
- When citing repository files or code locations, use the `【F:<path>†L<start>-L<end>】` pattern to align with project and tooling conventions.
- For command output captured during testing, reference the terminal chunk ID with `【<chunk_id>†L<start>-L<end>】`.
- Link to canonical documents (e.g., architecture, i18n workflow) instead of duplicating large explanations; cite them when summarising behaviour.

## Review & Maintenance
- Update this guide whenever documentation conventions change (e.g., adopting a different heading style or citation format).
- Cross-reference updates in docs/project_plan.md so sprint notes and future contributors are aware of the latest baseline.
