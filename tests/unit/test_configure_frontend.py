"""Unit tests for scripts/configure_frontend.py."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest


def _load_module():
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / "configure_frontend.py"
    spec = importlib.util.spec_from_file_location("configure_frontend", script_path)
    assert spec and spec.loader, "could not locate configure_frontend.py"
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(spec.name, module)
    spec.loader.exec_module(module)
    return module


configure_frontend = _load_module()


HTML = (
    "<!DOCTYPE html>\n"
    "<html><head>\n"
    "<meta charset=\"utf-8\" />\n"
    "<title>GreekTax</title>\n"
    "</head><body>hello</body></html>\n"
)


def test_inject_adds_meta_tag(tmp_path: Path) -> None:
    target = tmp_path / "index.html"
    target.write_text(HTML, encoding="utf-8")

    status = configure_frontend.configure(target, "https://api.example.com/v1")

    assert "injected" in status
    output = target.read_text(encoding="utf-8")
    assert '<meta data-api-base="https://api.example.com/v1" />' in output
    assert configure_frontend.MARKER_OPEN in output
    assert configure_frontend.MARKER_CLOSE in output
    assert output.index(configure_frontend.MARKER_OPEN) < output.index("</head>")


def test_inject_is_idempotent(tmp_path: Path) -> None:
    target = tmp_path / "index.html"
    target.write_text(HTML, encoding="utf-8")

    configure_frontend.configure(target, "https://first.example/v1")
    configure_frontend.configure(target, "https://second.example/v1")

    output = target.read_text(encoding="utf-8")
    assert output.count(configure_frontend.MARKER_OPEN) == 1
    assert '<meta data-api-base="https://second.example/v1" />' in output
    assert "first.example" not in output


def test_empty_api_base_removes_previous_injection(tmp_path: Path) -> None:
    target = tmp_path / "index.html"
    target.write_text(HTML, encoding="utf-8")

    configure_frontend.configure(target, "https://api.example.com/v1")
    status = configure_frontend.configure(target, "")

    assert "removed" in status
    output = target.read_text(encoding="utf-8")
    assert configure_frontend.MARKER_OPEN not in output
    assert "data-api-base" not in output


def test_empty_api_base_on_clean_file_is_a_noop(tmp_path: Path) -> None:
    target = tmp_path / "index.html"
    target.write_text(HTML, encoding="utf-8")

    status = configure_frontend.configure(target, "")

    assert "unchanged" in status
    assert target.read_text(encoding="utf-8") == HTML


def test_missing_head_close_tag_errors(tmp_path: Path) -> None:
    target = tmp_path / "index.html"
    target.write_text("<html><body>no head close</body></html>", encoding="utf-8")

    with pytest.raises(RuntimeError, match="could not find"):
        configure_frontend.configure(target, "https://api.example.com/v1")


def test_main_exits_nonzero_when_target_missing(tmp_path: Path) -> None:
    rc = configure_frontend.main(["--target", str(tmp_path / "absent.html")])
    assert rc == 1


def test_main_succeeds_with_env_var(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "index.html"
    target.write_text(HTML, encoding="utf-8")
    monkeypatch.setenv("GREEKTAX_API_BASE", "https://env.example/v1")

    rc = configure_frontend.main(["--target", str(target)])

    assert rc == 0
    output = target.read_text(encoding="utf-8")
    assert '<meta data-api-base="https://env.example/v1" />' in output


def test_main_with_unset_env_var_is_clean_noop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "index.html"
    target.write_text(HTML, encoding="utf-8")
    monkeypatch.delenv("GREEKTAX_API_BASE", raising=False)

    rc = configure_frontend.main(["--target", str(target)])

    assert rc == 0
    assert target.read_text(encoding="utf-8") == HTML


# ---- version_bundle tests ----

VERSIONED_HTML = (
    "<!DOCTYPE html>\n"
    "<html><head>\n"
    "<title>GreekTax</title>\n"
    "</head><body>\n"
    '<script type="module" src="./assets/scripts/main.js"></script>\n'
    "</body></html>\n"
)


def _stage_bundle(tmp_path: Path) -> Path:
    target = tmp_path / "index.html"
    target.write_text(VERSIONED_HTML, encoding="utf-8")
    scripts = tmp_path / "assets" / "scripts"
    (scripts / "ui").mkdir(parents=True)
    (scripts / "main.js").write_text(
        'import { bootstrapApp } from "./ui/app.js";\n'
        "bootstrapApp();\n",
        encoding="utf-8",
    )
    (scripts / "ui" / "app.js").write_text(
        'import { x } from "../helpers.js";\n'
        "export function bootstrapApp() { return x; }\n",
        encoding="utf-8",
    )
    (scripts / "helpers.js").write_text(
        "export const x = 1;\n",
        encoding="utf-8",
    )
    return target


def test_version_bundle_appends_versions_to_html_and_imports(tmp_path: Path) -> None:
    target = _stage_bundle(tmp_path)

    status = configure_frontend.version_bundle(target)

    assert "versioned" in status
    html = target.read_text(encoding="utf-8")
    main_js = (tmp_path / "assets" / "scripts" / "main.js").read_text("utf-8")
    app_js = (tmp_path / "assets" / "scripts" / "ui" / "app.js").read_text("utf-8")
    helpers = (tmp_path / "assets" / "scripts" / "helpers.js").read_text("utf-8")

    # HTML script tag gains a version.
    assert re.search(r'src="\./assets/scripts/main\.js\?v=[A-Za-z0-9]+"', html)
    # main.js's relative import gains a version.
    assert re.search(r'from "\./ui/app\.js\?v=[A-Za-z0-9]+"', main_js)
    # app.js's relative import gains a version.
    assert re.search(r'from "\.\./helpers\.js\?v=[A-Za-z0-9]+"', app_js)
    # helpers.js has no relative imports — should be untouched.
    assert helpers == "export const x = 1;\n"


def test_version_bundle_is_idempotent(tmp_path: Path) -> None:
    target = _stage_bundle(tmp_path)

    configure_frontend.version_bundle(target)
    after_first = target.read_text(encoding="utf-8")
    main_first = (tmp_path / "assets" / "scripts" / "main.js").read_text("utf-8")

    configure_frontend.version_bundle(target)
    after_second = target.read_text(encoding="utf-8")
    main_second = (tmp_path / "assets" / "scripts" / "main.js").read_text("utf-8")

    assert after_first == after_second
    assert main_first == main_second
    # Exactly one ?v= per import, not stacked.
    assert main_first.count("?v=") == 1


def test_version_bundle_changes_when_content_changes(tmp_path: Path) -> None:
    target = _stage_bundle(tmp_path)
    configure_frontend.version_bundle(target)
    html_before = target.read_text(encoding="utf-8")
    match_before = re.search(r"main\.js\?v=([A-Za-z0-9]+)", html_before)
    assert match_before
    version_before = match_before.group(1)

    # Modify a JS file and re-run.
    helpers = tmp_path / "assets" / "scripts" / "helpers.js"
    helpers.write_text("export const x = 2;\n", encoding="utf-8")
    configure_frontend.version_bundle(target)
    html_after = target.read_text(encoding="utf-8")
    match_after = re.search(r"main\.js\?v=([A-Za-z0-9]+)", html_after)
    assert match_after
    version_after = match_after.group(1)

    assert version_before != version_after


def test_version_bundle_skips_when_scripts_dir_missing(tmp_path: Path) -> None:
    target = tmp_path / "index.html"
    target.write_text(VERSIONED_HTML, encoding="utf-8")

    status = configure_frontend.version_bundle(target)

    assert "skipped" in status
    # File is unchanged.
    assert target.read_text(encoding="utf-8") == VERSIONED_HTML


def test_main_runs_both_steps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = _stage_bundle(tmp_path)
    monkeypatch.setenv("GREEKTAX_API_BASE", "https://api.example.com/v1")

    rc = configure_frontend.main(["--target", str(target)])

    assert rc == 0
    html = target.read_text(encoding="utf-8")
    # API base meta tag.
    assert '<meta data-api-base="https://api.example.com/v1" />' in html
    # Cache-bust query.
    assert re.search(r'src="\./assets/scripts/main\.js\?v=[A-Za-z0-9]+"', html)
