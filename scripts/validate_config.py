#!/usr/bin/env python3
"""Validate YAML configuration files without requiring an editable install."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the src directory is available on the import path when running directly
# from a Git checkout. This mirrors the convenience provided in ``tests/`` so
# contributors can execute the validator without first installing the package.
REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from greektax.backend.config.validator import main


if __name__ == "__main__":
    raise SystemExit(main())
