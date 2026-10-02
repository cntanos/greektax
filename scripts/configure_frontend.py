#!/usr/bin/env python3
"""Version the deployed frontend's JavaScript so browsers never use stale files.

Run from the deploy hook (``.cpanel.yml``) after the static files have been
copied into the docroot. It computes a short content hash from every
JavaScript file under ``<docroot>/assets/scripts/`` and appends ``?v=<hash>``
to (a) the local ``<script src="./assets/scripts/...">`` tags in
``index.html`` and (b) every relative ``import`` / ``export ... from`` /
``import("...")`` in those files. When the bundle changes, the hash changes,
so the browser fetches the new files instead of serving stale ones from its
long-lived cache.

The step is idempotent: any previous version query is stripped before the new
one is written.

Usage::

    python3 scripts/configure_frontend.py --target /path/to/index.html

Exit codes:
    0 on success
    1 on usage/IO errors
"""

import argparse
import hashlib
import re
import sys
from pathlib import Path
from typing import List, Optional

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
        description="Append a cache-busting version to the deployed frontend's scripts.",
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=Path("src/frontend/index.html"),
        help="path to the index.html that will be served (default: %(default)s)",
    )
    args = parser.parse_args(argv)

    if not args.target.exists():
        print("error: " + str(args.target) + " does not exist", file=sys.stderr)
        return 1
    print(version_bundle(args.target))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
