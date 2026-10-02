#!/bin/bash
# SessionStart hook for Claude Code on the web: installs the Python
# and frontend test (Node) dependencies so pytest, ruff, mypy, vulture and
# `npm run test:frontend` work out of the box in cloud sessions.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/../..}"
PROJECT_DIR="$PWD"
VENV="$PROJECT_DIR/.venv"

# Use a project venv: the container's Debian-managed packages (e.g. blinker)
# cannot be upgraded in place by pip.
if [ ! -x "$VENV/bin/python" ]; then
  python3 -m venv "$VENV"
fi

# Python dependencies + dev tooling (mirrors .github/workflows/ci.yml).
"$VENV/bin/python" -m pip install --quiet --disable-pip-version-check -r requirements-dev.txt
"$VENV/bin/python" -m pip install --quiet --disable-pip-version-check --no-deps -e .

# Frontend optional dev deps (jsdom, acorn). Without them the JSDOM/AST
# tests skip instead of running.
npm install --no-audit --no-fund --no-package-lock --no-update-notifier --loglevel=error

# Put the venv first on PATH for the rest of the session.
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  {
    echo "export VIRTUAL_ENV=\"$VENV\""
    echo "export PATH=\"$VENV/bin:\$PATH\""
  } >> "$CLAUDE_ENV_FILE"
fi
