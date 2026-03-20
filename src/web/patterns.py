from __future__ import annotations

import copy
import uuid
from typing import Any
import unicodedata

import yaml

from src.web.editor_base import BaseEditor, split_csv


class PatternsEditor(BaseEditor):
    kind = "Patterns"
    dir_name = "patterns"
    collection_key = "patterns"

    def load_state(self, config_dir: str, relative_path: str) -> dict[str, Any]:
        path = self.safe_path(config_dir, relative_path)
        if path is None or not path.exists():
            raise FileNotFoundError(relative_path)

        with path.open("r", encoding="utf-8") as handle:
            document = yaml.safe_load(handle) or {}

        if document.get("kind") != "Patterns":
            raise ValueError(f"{relative_path} is not a Patterns config")

        return {
            "path": relative_path,
            "kind": "Patterns",
            "patterns": _patterns_from_document(document.get("patterns", [])),
        }

    def to_yaml(self, state: dict[str, Any]) -> str:
        document = {
            "kind": "Patterns",
            "patterns": _document_patterns(state.get("patterns", [])),
        }
        return yaml.safe_dump(document, sort_keys=False, allow_unicode=True)

    def _blank_item(self) -> dict[str, Any]:
        return {
            "id": uuid.uuid4().hex,
            "name": "",
            "ref": "",
            "pattern_text": "",
            "test_includes": "",
            "test_excludes": "",
            "test_results": None,
        }

    def _run_test(self, item: dict[str, Any], registry: Any) -> dict:
        ref = item.get("ref", "").strip()
        includes = split_csv(item.get("test_includes", ""))
        excludes = split_csv(item.get("test_excludes", ""))
        return registry.test_pattern(ref, includes, excludes)

    def _update_items_from_form(
        self, patterns: list[dict[str, Any]], form: Any
    ) -> list[dict[str, Any]]:
        updated: list[dict[str, Any]] = []
        for pattern in patterns:
            pattern_id = pattern["id"]
            current = copy.deepcopy(pattern)
            current["name"] = form.get(
                f"name-{pattern_id}", current.get("name", "")
            ).strip()
            current["ref"] = form.get(
                f"ref-{pattern_id}", current.get("ref", "")
            ).strip()
            current["pattern_text"] = form.get(
                f"pattern_text-{pattern_id}", current.get("pattern_text", "")
            ).strip()
            current["test_includes"] = form.get(
                f"test_includes-{pattern_id}", current.get("test_includes", "")
            ).strip()
            current["test_excludes"] = form.get(
                f"test_excludes-{pattern_id}", current.get("test_excludes", "")
            ).strip()
            updated.append(current)
        return updated


def _patterns_from_document(document_patterns: list[Any]) -> list[dict[str, Any]]:
    patterns: list[dict[str, Any]] = []
    for item in document_patterns:
        if not isinstance(item, dict) or len(item) != 1:
            continue
        name, value = next(iter(item.items()))
        if not isinstance(value, dict):
            continue
        raw_pattern = value.get("pattern", "")
        norm_pattern = unicodedata.normalize("NFKD", str(raw_pattern))
        includes = value.get("test_includes", [])
        excludes = value.get("test_excludes", [])
        pattern = {
            "id": uuid.uuid4().hex,
            "name": str(name),
            "ref": str(value.get("_ref", "")),
            "pattern_text": norm_pattern,
            "test_includes": ", ".join(str(entry) for entry in includes if str(entry)),
            "test_excludes": ", ".join(str(entry) for entry in excludes if str(entry)),
        }
        patterns.append(pattern)
    return patterns


def _document_patterns(patterns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    document_patterns: list[dict[str, Any]] = []
    for pattern in patterns:
        name = pattern.get("name", "").strip()
        if not name:
            continue
        entry: dict[str, Any] = {}
        pattern_value = pattern.get("pattern_text", "").strip()
        if pattern_value:
            entry["pattern"] = pattern_value
        ref = pattern.get("ref", "").strip()
        if ref:
            entry["_ref"] = ref
        includes = split_csv(pattern.get("test_includes", ""))
        excludes = split_csv(pattern.get("test_excludes", ""))
        if includes:
            entry["test_includes"] = includes
        if excludes:
            entry["test_excludes"] = excludes
        document_patterns.append({name: entry})
    return document_patterns
