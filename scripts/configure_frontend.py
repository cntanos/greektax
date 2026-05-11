#!/usr/bin/env python3
"""Inject deployment-specific configuration into the served frontend.

Two responsibilities, both run from a deploy hook after the static files
have been copied into the docroot:

1. **API base injection.** Reads ``GREEKTAX_API_BASE`` from the environment
   and writes a ``<meta data-api-base="..." />`` tag into the deployed
   ``index.html`` so the frontend talks to the right backend host.
2. **Cache-buster versioning.** Computes a short content hash from every
   JavaScript file under ``<docroot>/assets/scripts/`` and appends
   ``?v=<hash>`` to (a) the ``<script type="module" src="...">`` tag in
   ``index.html`` and (b) every relative ``import`` / ``export ... from``
   in those JS files. When the bundle content changes, the hash changes,
   so the browser fetches the new files instead of serving stale ones
   from its long-lived ``immutable`` cache.

Both steps are idempotent: any previous injection or version query is
stripped before the new one is written, so re-running the script after a
no-op deploy produces the same output as the first run.

Usage::

    GREEKTAX_API_BASE=https://example.com/api/v1 \\
        python3 scripts/configure_frontend.py --target /path/to/index.html

Exit codes:
    0 on success (including no-op paths)
    1 on usage/IO errors
"""

import argparse
import hashlib
import os
import re
import sys
from pathlib import Path
from typing import List, Optional

MARKER_OPEN = "<!-- @greektax/api-base:start -->"
MARKER_CLOSE = "<!-- @greektax/api-base:end -->"
INJECTION_PATTERN = re.compile(
    re.escape(MARKER_OPEN) + r".*?" + re.escape(MARKER_CLOSE) + r"\s*",
    re.DOTALL,
)
HEAD_CLOSE = "</head>"

# Match `"..."` or `'...'` containing a relative path ending in `.js`,
# with an optional pre-existing `?v=<hash>` query.
JS_IMPORT_PATH_PATTERN = re.compile(
    r"""(?P<quote>["'])(?P<path>\.{1,2}/[^"'?\s]*\.js)(?:\?v=[A-Za-z0-9]+)?(?P=quote)"""
)

# Match any local script tag in index.html, optionally already versioned.
# Covers both the ES-module entrypoint (./assets/scripts/main.js) and any
# classic-script siblings such as ./assets/scripts/translations.generated.js.
SCRIPT_TAG_PATTERN = re.compile(
    r"""(?P<prefix><script\b[^>]*?src=")(?P<path>\./assets/scripts/[^"?\s]+\.js)"""
    r"""(?:\?v=[A-Za-z0-9]+)?(?P<suffix>"[^>]*></script>)"""
)


def _strip_previous(html: str) -> str:
    return INJECTION_PATTERN.sub("", html)


def _build_block(api_base: str) -> str:
    return (
        "    " + MARKER_OPEN + "\n"
        '    <meta data-api-base="' + api_base + '" />\n'
        "    " + MARKER_CLOSE + "\n  "
    )


def configure(target: Path, api_base: str) -> str:
    """Inject (or remove) the meta tag in ``target``."""
    html = target.read_text(encoding="utf-8")
    stripped = _strip_previous(html)

    if not api_base:
        if stripped != html:
            target.write_text(stripped, encoding="utf-8")
            return "removed previous data-api-base injection"
        return "no data-api-base configured; left target unchanged"

    head_idx = stripped.find(HEAD_CLOSE)
    if head_idx == -1:
        raise RuntimeError("could not find " + repr(HEAD_CLOSE) + " in " + str(target))
    new_html = stripped[:head_idx] + _build_block(api_base) + stripped[head_idx:]
    target.write_text(new_html, encoding="utf-8")
    return "injected data-api-base=" + api_base


def _strip_versions_in_js(text: str) -> str:
    return JS_IMPORT_PATH_PATTERN.sub(
        lambda m: m.group("quote") + m.group("path") + m.group("quote"),
        text,
    )


def _strip_version_in_script_tag(text: str) -> str:
    return SCRIPT_TAG_PATTERN.sub(
        lambda m: m.group("prefix") + m.group("path") + m.group("suffix"),
        text,
    )


def _apply_version_to_js(text: str, version: str) -> str:
    return JS_IMPORT_PATH_PATTERN.sub(
        lambda m: (
            m.group("quote") + m.group("path") + "?v=" + version + m.group("quote")
        ),
        text,
    )


def _apply_version_to_script_tag(text: str, version: str) -> str:
    return SCRIPT_TAG_PATTERN.sub(
        lambda m: (
            m.group("prefix") + m.group("path") + "?v=" + version + m.group("suffix")
        ),
        text,
    )


def version_bundle(target: Path) -> str:
    """Append ``?v=<hash>`` to every relative import and to the loader tag.

    The hash is the first 12 hex chars of the SHA-256 over every JS file
    under ``<target.parent>/assets/scripts/`` (sorted by relative path,
    after stripping any existing ``?v=...`` from import statements). The
    same hash is then appended to all relative imports and to the
    ``<script type="module" src="...">`` tag in ``target``.

    Returns a status string. If the scripts directory does not exist,
    returns a short message and makes no changes (this is the common
    case when running against a test fixture or unconfigured target).
    """
    scripts_dir = target.parent / "assets" / "scripts"
    if not scripts_dir.is_dir():
        return "skipped version_bundle: " + str(scripts_dir) + " not present"

    js_files = sorted(
        scripts_dir.rglob("*.js"),
        key=lambda p: p.relative_to(scripts_dir).as_posix(),
    )
    if not js_files:
        return "skipped version_bundle: no .js files under " + str(scripts_dir)

    # Strip any pre-existing ?v=... so the hash is content-stable.
    cleaned_sources = {}
    for path in js_files:
        original = path.read_text(encoding="utf-8")
        cleaned = _strip_versions_in_js(original)
        cleaned_sources[path] = cleaned

    digest = hashlib.sha256()
    for path in js_files:
        rel = path.relative_to(scripts_dir).as_posix()
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(cleaned_sources[path].encode("utf-8"))
    version = digest.hexdigest()[:12]

    rewrites = 0
    for path, cleaned in cleaned_sources.items():
        versioned = _apply_version_to_js(cleaned, version)
        if versioned != path.read_text(encoding="utf-8"):
            path.write_text(versioned, encoding="utf-8")
            rewrites += 1

    html = target.read_text(encoding="utf-8")
    html_clean = _strip_version_in_script_tag(html)
    html_versioned = _apply_version_to_script_tag(html_clean, version)
    if html_versioned != html:
        target.write_text(html_versioned, encoding="utf-8")
        rewrites += 1

    return "versioned " + str(len(js_files)) + " JS files + index.html with ?v=" + version


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inject GREEKTAX_API_BASE and cache-buster version into a deployed index.html.",
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=Path("src/frontend/index.html"),
        help="path to the index.html that will be served (default: %(default)s)",
    )
    args = parser.parse_args(argv)

    api_base = (os.environ.get("GREEKTAX_API_BASE") or "").strip()

    if not args.target.exists():
        print("error: " + str(args.target) + " does not exist", file=sys.stderr)
        return 1
    try:
        status = configure(args.target, api_base)
    except RuntimeError as exc:
        print("error: " + str(exc), file=sys.stderr)
        return 1
    print(status)
    try:
        bundle_status = version_bundle(args.target)
    except RuntimeError as exc:
        print("error: " + str(exc), file=sys.stderr)
        return 1
    print(bundle_status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
