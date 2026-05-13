"""Frontend translation catalogue consistency checks."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Iterable, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
TRANSLATIONS_DIR = REPO_ROOT / "src" / "greektax" / "translations"
FRONTEND_HTML = REPO_ROOT / "src" / "frontend" / "index.html"
EMBEDDED_BUNDLE = REPO_ROOT / "src" / "frontend" / "assets" / "scripts" / "translations.generated.js"


def _flatten_catalogue(catalogue: Dict[str, object], prefix: str = "") -> Iterable[Tuple[str, str]]:
    for key, value in catalogue.items():
        scoped_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            yield from _flatten_catalogue(value, scoped_key)
        else:
            yield scoped_key, str(value)


def _load_frontend_catalogue(locale: str) -> Dict[str, object]:
    payload = json.loads((TRANSLATIONS_DIR / f"{locale}.json").read_text(encoding="utf-8"))
    frontend = payload.get("frontend")
    if not isinstance(frontend, dict):  # pragma: no cover - defensive guard
        raise AssertionError(f"Locale {locale!r} missing frontend catalogue")
    return frontend


def _read_embedded_translations() -> Dict[str, object]:
    content = EMBEDDED_BUNDLE.read_text(encoding="utf-8")
    match = re.search(r"const translations = (\{.*?\});\s*\n", content, re.DOTALL)
    if not match:  # pragma: no cover - corrupted bundle
        raise AssertionError("Unable to parse embedded translations bundle")
    return json.loads(match.group(1))


def test_embedded_bundle_matches_source_catalogues() -> None:
    """The generated frontend bundle should mirror the shared JSON catalogues."""

    embedded = _read_embedded_translations()
    source = {
        path.stem: _load_frontend_catalogue(path.stem)
        for path in sorted(TRANSLATIONS_DIR.glob("*.json"))
    }

    assert embedded == source


def test_all_frontend_keys_have_translations() -> None:
    """Every data-i18n key in the HTML shell should resolve for each locale."""

    html = FRONTEND_HTML.read_text(encoding="utf-8")
    key_pattern = re.compile(r"data-i18n-key=\"([^\"]+)\"")
    placeholder_pattern = re.compile(r"data-i18n-placeholder=\"([^\"]+)\"")
    all_keys = set(key_pattern.findall(html)) | set(placeholder_pattern.findall(html))
    assert all_keys, "No translation keys discovered in frontend markup"

    for path in sorted(TRANSLATIONS_DIR.glob("*.json")):
        locale = path.stem
        catalogue = dict(_flatten_catalogue(_load_frontend_catalogue(locale)))
        missing = sorted(key for key in all_keys if key not in catalogue)
        assert not missing, f"Locale {locale} missing translations for: {', '.join(missing[:5])}"
