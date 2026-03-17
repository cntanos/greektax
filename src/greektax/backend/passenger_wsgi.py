"""WSGI entrypoint for Passenger-style hosts.

This module is production-facing code, not scaffolding. Passenger and similar
hosts may import it directly from ``src/greektax/backend`` where the repository
root is not on ``sys.path``. The path adjustment below keeps
``greektax.backend.app.create_app`` importable in that environment.
"""

import sys
from pathlib import Path

# Compute ``.../src`` from ``.../src/greektax/backend/passenger_wsgi.py``.
SRC_DIR = Path(__file__).resolve().parents[2]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from greektax.backend.app import create_app  # noqa: E402

application = create_app()
