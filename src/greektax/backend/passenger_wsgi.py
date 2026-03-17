"""WSGI entrypoint for Passenger-compatible deployments.

Flask/Gunicorn docs commonly reference ``from myproject import create_app``.
In this project the factory lives at ``greektax.backend.app.create_app`` under
``src/``.
"""

import sys
from pathlib import Path

# Hosting environments may execute this file directly from
# ``src/greektax/backend`` without adding the repository ``src/`` directory to
# ``sys.path``. Prepend it so absolute imports like
# ``from greektax.backend.app import create_app`` always resolve.
SRC_DIR = Path(__file__).resolve().parents[2]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from greektax.backend.app import (  # noqa: E402
    create_app,  # app factory in src/greektax/backend/app/__init__.py
)

application = create_app()
