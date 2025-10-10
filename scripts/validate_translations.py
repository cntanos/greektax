#!/usr/bin/env python3
"""Validate translation catalogues and emit shared metadata artifacts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
TRANSLATIONS_DIR = REPO_ROOT / "src" / "greektax" / "translations"
BACKEND_DIR = REPO_ROOT / "src" / "greektax" / "backend"
FRONTEND_DIR = REPO_ROOT / "src" / "frontend"
CONFIG_DATA_DIR = REPO_ROOT / "src" / "greektax" / "backend" / "config" / "data"
METADATA_PATH = TRANSLATIONS_DIR / "metadata.json"
FRONTEND_TYPES_PATH = REPO_ROOT / "src" / "frontend" / "types" / "translations.d.ts"

PLACEHOLDER_PATTERN = re.compile(r"{{\s*([a-zA-Z0-9_.-]+)\s*}}")


class ValidationError(Exception):
    """Raised when validation detects unrecoverable issues."""


def _flatten_messages(tree: dict, prefix: str = "") -> dict[str, str]:
    items: dict[str, str] = {}
    for key, value in tree.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            items.update(_flatten_messages(value, path))
        else:
            items[path] = "" if value is None else str(value)
    return items


def _load_translation_payloads() -> tuple[list[str], dict[str, dict[str, dict[str, str]]]]:
    locales: list[str] = []
    catalogues: dict[str, dict[str, dict[str, str]]] = {}

    if not TRANSLATIONS_DIR.is_dir():
        raise ValidationError(f"Missing translations directory: {TRANSLATIONS_DIR}")

    for path in sorted(TRANSLATIONS_DIR.glob("*.json")):
        if path.name == "metadata.json":
            continue
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)

        if not isinstance(payload, dict):
            raise ValidationError(f"Unexpected payload format in {path}")

        backend = payload.get("backend") or {}
        frontend = payload.get("frontend") or {}
        if not isinstance(backend, dict) or not isinstance(frontend, dict):
            raise ValidationError(f"Translation payload must define backend/frontend mappings: {path}")

        locales.append(path.stem)
        catalogues[path.stem] = {
            "backend": _flatten_messages(backend),
            "frontend": _flatten_messages(frontend),
        }

    if not locales:
        raise ValidationError("No translation catalogues discovered")

    return locales, catalogues


def _collect_placeholders(catalogues: dict[str, dict[str, dict[str, str]]]) -> dict[str, dict[str, dict[str, set[str]]]]:
    placeholders: dict[str, dict[str, dict[str, set[str]]]] = {
        "backend": defaultdict(dict),
        "frontend": defaultdict(dict),
    }

    for locale, sections in catalogues.items():
        for section in ("backend", "frontend"):
            for key, message in sections[section].items():
                matches = set(PLACEHOLDER_PATTERN.findall(message))
                placeholders[section].setdefault(key, {})[locale] = matches

    return placeholders


def _placeholder_inconsistencies(placeholders: dict[str, dict[str, dict[str, set[str]]]]) -> list[str]:
    inconsistencies: list[str] = []
    for section, keys in placeholders.items():
        for key, locale_map in keys.items():
            unique_sets = {frozenset(values) for values in locale_map.values()}
            if len(unique_sets) <= 1:
                continue
            details = ", ".join(
                f"{locale}={{{', '.join(sorted(values))}}}"
                for locale, values in sorted(locale_map.items())
            )
            inconsistencies.append(f"{section}:{key} placeholders differ: {details}")
    return inconsistencies


def _missing_keys(catalogues: dict[str, dict[str, dict[str, str]]], base_locale: str) -> list[str]:
    issues: list[str] = []
    base = catalogues.get(base_locale)
    if not base:
        return issues

    for section in ("backend", "frontend"):
        expected = set(base[section])
        for locale, payload in catalogues.items():
            missing = expected - set(payload[section])
            if missing:
                issues.append(
                    f"Locale '{locale}' missing {len(missing)} {section} keys: {', '.join(sorted(missing))}"
                )
    return issues


def _gather_frontend_usage() -> tuple[set[str], set[str], set[str]]:
    used_keys: set[str] = set()
    wildcard_prefixes: set[str] = set()
    section_consumers: set[str] = set()

    js_files = list(FRONTEND_DIR.rglob("*.js"))
    html_files = list(FRONTEND_DIR.rglob("*.html"))
    all_files = js_files + html_files

    section_pattern = re.compile(r"getMessagesSection\([^,]+,\s*['\"]([a-zA-Z0-9_.-]+)['\"]")
    call_pattern = re.compile(r"(?:\bt|\btranslate)\(\s*(['\"])([^\1]+?)\1")
    data_attr_pattern = re.compile(r"data-i18n-(?:key|placeholder)=\"([^\"]+)\"")
    template_pattern = re.compile(r"([a-zA-Z0-9_.-]+)\.\$\{")
    concat_pattern = re.compile(r"['\"]([a-zA-Z0-9_.-]+)\.['\"]\s*\+")

    for path in all_files:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue

        for match in call_pattern.finditer(text):
            used_keys.add(match.group(2))

        for match in section_pattern.finditer(text):
            section_consumers.add(match.group(1))

        for match in data_attr_pattern.finditer(text):
            used_keys.add(match.group(1))

        for match in template_pattern.finditer(text):
            wildcard_prefixes.add(match.group(1) + ".")

        for match in concat_pattern.finditer(text):
            wildcard_prefixes.add(match.group(1) + ".")

    return used_keys, wildcard_prefixes, section_consumers


def _visit_python_ast(tree, callback) -> None:
    import ast

    class _Visitor(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call) -> None:  # type: ignore[override]
            target_name: str | None = None
            if isinstance(node.func, ast.Name) and node.func.id == "translator":
                target_name = "translator"
            elif isinstance(node.func, ast.Attribute) and node.func.attr == "translator":
                target_name = node.func.attr

            if target_name and node.args:
                callback(node.args[0])

            self.generic_visit(node)

    _Visitor().visit(tree)


def _collect_backend_usage() -> tuple[set[str], set[str]]:
    import ast

    used_keys: set[str] = set()
    wildcard_prefixes: set[str] = set()

    def handle_arg(node: ast.AST) -> None:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            used_keys.add(node.value)
            return

        if isinstance(node, ast.JoinedStr):
            prefix_parts: list[str] = []
            for value in node.values:
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    prefix_parts.append(value.value)
                else:
                    break
            if prefix_parts:
                prefix = "".join(prefix_parts)
                if prefix:
                    wildcard_prefixes.add(prefix)

    for path in BACKEND_DIR.rglob("*.py"):
        try:
            source = path.read_text(encoding="utf-8")
        except OSError:
            continue

        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue

        _visit_python_ast(tree, handle_arg)

    return used_keys, wildcard_prefixes


def _collect_config_usage() -> set[str]:
    used: set[str] = set()

    if not CONFIG_DATA_DIR.is_dir():
        return used

    def traverse(node: object, key_hint: str | None = None) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                traverse(value, key_hint=key)
        elif isinstance(node, list):
            for item in node:
                traverse(item, key_hint=key_hint)
        elif isinstance(node, str):
            if key_hint and key_hint.endswith("_key"):
                used.add(node)
            elif key_hint and key_hint.endswith("_keys"):
                used.add(node)

    for yaml_path in CONFIG_DATA_DIR.glob("*.yaml"):
        try:
            with yaml_path.open("r", encoding="utf-8") as handle:
                data = yaml.safe_load(handle)
        except (OSError, yaml.YAMLError):
            continue

        traverse(data)

    return used


def _mark_section_usage(keys: Iterable[str], sections: set[str]) -> set[str]:
    used: set[str] = set()
    for key in keys:
        for section in sections:
            if key == section or key.startswith(f"{section}."):
                used.add(key)
                break
    return used


def _detect_unused_keys(
    catalogues: dict[str, dict[str, dict[str, str]]],
    base_locale: str,
) -> tuple[list[str], list[str]]:
    frontend_catalogue = catalogues[base_locale]["frontend"]
    backend_catalogue = catalogues[base_locale]["backend"]

    frontend_keys = set(frontend_catalogue)
    backend_keys = set(backend_catalogue)

    frontend_used_literals, frontend_wildcards, sections = _gather_frontend_usage()
    frontend_used = set(frontend_used_literals)
    frontend_used |= _mark_section_usage(frontend_keys, sections)

    backend_used_literals, backend_wildcards = _collect_backend_usage()
    backend_config_usage = _collect_config_usage()

    unused_frontend = []
    for key in sorted(frontend_keys):
        if key in frontend_used:
            continue
        if any(key.startswith(prefix) for prefix in frontend_wildcards):
            continue
        unused_frontend.append(key)

    unused_backend = []
    for key in sorted(backend_keys):
        if key in backend_used_literals or key in backend_config_usage:
            continue
        if any(key.startswith(prefix) for prefix in backend_wildcards):
            continue
        unused_backend.append(key)

    return unused_frontend, unused_backend


def _write_metadata(
    locales: Iterable[str],
    catalogues: dict[str, dict[str, dict[str, str]]],
    placeholders: dict[str, dict[str, dict[str, set[str]]]],
    base_locale: str,
    metadata_path: Path,
) -> dict:
    ordered_locales = sorted(locales)
    default_frontend_locale = next(
        (locale for locale in ordered_locales if locale != base_locale),
        base_locale,
    )

    def _placeholder_snapshot(section: str) -> dict[str, list[str]]:
        snapshot: dict[str, list[str]] = {}
        for key in catalogues[base_locale][section]:
            locale_map = placeholders[section].get(key, {})
            merged = sorted(set().union(*locale_map.values())) if locale_map else []
            if merged:
                snapshot[key] = merged
        return snapshot

    metadata = {
        "locales": ordered_locales,
        "base_locale": base_locale,
        "default_frontend_locale": default_frontend_locale,
        "frontend": {
            "keys": sorted(catalogues[base_locale]["frontend"].keys()),
            "placeholders": _placeholder_snapshot("frontend"),
        },
        "backend": {
            "keys": sorted(catalogues[base_locale]["backend"].keys()),
            "placeholders": _placeholder_snapshot("backend"),
        },
    }

    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return metadata


def _write_types(metadata: dict, placeholders: dict[str, dict[str, dict[str, set[str]]]]) -> None:
    lines: list[str] = [
        "// This file is auto-generated by scripts/validate_translations.py.",
        "// Do not edit manually.",
        "",
    ]

    locales = metadata["locales"]
    base_locale = metadata["base_locale"]
    default_locale = metadata["default_frontend_locale"]
    frontend_keys: list[str] = metadata["frontend"]["keys"]
    backend_keys: list[str] = metadata["backend"]["keys"]

    def _write_union(name: str, values: list[str]) -> None:
        if not values:
            lines.append(f"export type {name} = never;")
            return
        if len(values) == 1:
            lines.append(f"export type {name} = '{values[0]}';")
            return
        lines.append(f"export type {name} =")
        for value in values:
            lines.append(f"  | '{value}'")
        lines.append(";")

    _write_union("AvailableLocale", locales)
    lines.append(f"export type BaseLocale = '{base_locale}';")
    lines.append(f"export type DefaultFrontendLocale = '{default_locale}';")
    _write_union("FrontendMessageKey", frontend_keys)
    _write_union("BackendMessageKey", backend_keys)
    lines.append("")

    def _placeholder_lines(section: str) -> list[str]:
        entries: list[str] = []
        for key in metadata[section]["keys"]:
            sets_by_locale = placeholders[section].get(key, {})
            merged = sorted(set().union(*sets_by_locale.values())) if sets_by_locale else []
            if not merged:
                continue
            joined = ", ".join(f"'{value}'" for value in merged)
            entries.append(f"  '{key}': readonly [{joined}];")
        return entries

    lines.append("export interface FrontendPlaceholderMap {")
    placeholder_entries = _placeholder_lines("frontend")
    if placeholder_entries:
        lines.extend(placeholder_entries)
    lines.append("}")
    lines.append("")

    lines.append("export interface BackendPlaceholderMap {")
    backend_entries = _placeholder_lines("backend")
    if backend_entries:
        lines.extend(backend_entries)
    lines.append("}")

    FRONTEND_TYPES_PATH.parent.mkdir(parents=True, exist_ok=True)
    FRONTEND_TYPES_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fail-on-unused", action="store_true", help="Exit with an error if unused keys are found")
    args = parser.parse_args(argv)

    locales, catalogues = _load_translation_payloads()
    base_locale = "en" if "en" in locales else locales[0]

    placeholders = _collect_placeholders(catalogues)
    inconsistencies = _placeholder_inconsistencies(placeholders)
    missing = _missing_keys(catalogues, base_locale)
    unused_frontend, unused_backend = _detect_unused_keys(catalogues, base_locale)

    metadata = _write_metadata(locales, catalogues, placeholders, base_locale, METADATA_PATH)
    _write_types(metadata, placeholders)

    if inconsistencies:
        for issue in inconsistencies:
            print(f"[placeholder] {issue}")

    if missing:
        for issue in missing:
            print(f"[missing] {issue}")

    if unused_frontend:
        print("[unused] Front-end keys:")
        for key in unused_frontend:
            print(f"  - {key}")

    if unused_backend:
        print("[unused] Backend keys:")
        for key in unused_backend:
            print(f"  - {key}")

    if inconsistencies or missing or ((unused_frontend or unused_backend) and args.fail_on_unused):
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

