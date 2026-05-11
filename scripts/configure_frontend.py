#!/usr/bin/env python3
"""Inject deployment-specific configuration into the served frontend.

Reads ``GREEKTAX_API_BASE`` from the environment and injects a
``<meta data-api-base="..." />`` tag into a deployed ``index.html`` so the
frontend points its API calls at the right backend host. The source
``src/frontend/index.html`` stays deployment-agnostic.

Intended to run from a deploy hook (cPanel ``.cpanel.yml``, GitHub
Actions, etc.) after the static files have been placed in the docroot.
Re-running is safe: any previous injection is replaced. When the env
var is unset or empty, any previous injection is removed so the
frontend falls back to its same-origin default.

Usage::

    GREEKTAX_API_BASE=https://example.com/api/v1 \\
        python scripts/configure_frontend.py --target /path/to/index.html

Exit codes:
    0 on success (including the env-unset cleanup path)
    1 on usage/IO errors
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

MARKER_OPEN = "<!-- @greektax/api-base:start -->"
MARKER_CLOSE = "<!-- @greektax/api-base:end -->"
INJECTION_PATTERN = re.compile(
    re.escape(MARKER_OPEN) + r".*?" + re.escape(MARKER_CLOSE) + r"\s*",
    re.DOTALL,
)
HEAD_CLOSE = "</head>"


def _strip_previous(html: str) -> str:
    return INJECTION_PATTERN.sub("", html)


def _build_block(api_base: str) -> str:
    return (
        f"    {MARKER_OPEN}\n"
        f'    <meta data-api-base="{api_base}" />\n'
        f"    {MARKER_CLOSE}\n  "
    )


def configure(target: Path, api_base: str) -> str:
    """Inject (or remove) the meta tag in ``target``.

    Returns a short status string for logging. Raises ``RuntimeError``
    if the target lacks a ``</head>`` tag and an injection is needed.
    """
    html = target.read_text(encoding="utf-8")
    stripped = _strip_previous(html)

    if not api_base:
        if stripped != html:
            target.write_text(stripped, encoding="utf-8")
            return "removed previous data-api-base injection"
        return "no data-api-base configured; left target unchanged"

    head_idx = stripped.find(HEAD_CLOSE)
    if head_idx == -1:
        raise RuntimeError(f"could not find {HEAD_CLOSE!r} in {target}")
    new_html = stripped[:head_idx] + _build_block(api_base) + stripped[head_idx:]
    target.write_text(new_html, encoding="utf-8")
    return f"injected data-api-base={api_base}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inject GREEKTAX_API_BASE into a deployed index.html.",
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
        print(f"error: {args.target} does not exist", file=sys.stderr)
        return 1
    try:
        status = configure(args.target, api_base)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
