"""Test configuration utilities."""

import sys
from pathlib import Path

# Ensure the ``src`` directory is importable when tests are executed without an
# editable install. This keeps developer experience smooth for first-time
# contributors running ``pytest`` directly in VS Code.
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
