"""Unit tests for scripts/configure_frontend.py."""

from __future__ import annotations

import importlib.util
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
