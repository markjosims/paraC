from __future__ import annotations

import copy
import json
import uuid
from pathlib import Path
from typing import Any

import yaml

from src.web.configs import load_uploaded_config_entry, save_uploaded_config_text, safe_file_path


PATTERNS_DIR_NAME = "patterns"


def safe_patterns_path(config_dir: str, relative_path: str) -> Path | None:
    path = safe_file_path(config_dir, relative_path)
    if path is None:
        return None
    if PATTERNS_DIR_NAME not in path.parts:
        return None
    return path


def new_patterns_state(relative_path: str = "") -> dict[str, Any]:
    return {
        "path": relative_path,
        "kind": "Patterns",
        "patterns": [],
    }


def load_patterns_state(config_dir: str, relative_path: str) -> dict[str, Any]:
    path = safe_patterns_path(config_dir, relative_path)
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


def load_uploaded_patterns_state(token: str, relative_path: str) -> dict[str, Any]:
    document = load_uploaded_config_entry(token, relative_path)["parsed"]
    if not isinstance(document, dict) or document.get("kind") != "Patterns":
        raise ValueError(f"{relative_path} is not a Patterns config")

    return {
        "path": relative_path,
        "kind": "Patterns",
        "patterns": _patterns_from_document(document.get("patterns", [])),
    }


def state_from_json(payload: str | None) -> dict[str, Any]:
    if not payload:
        return new_patterns_state()
    state = json.loads(payload)
    state.setdefault("kind", "Patterns")
    state.setdefault("path", "")
    state.setdefault("patterns", [])
    return _ensure_ids(state)


def state_to_json(state: dict[str, Any]) -> str:
    return json.dumps(state, ensure_ascii=False)


def update_state_from_form(state: dict[str, Any], form: Any) -> dict[str, Any]:
    updated = copy.deepcopy(state)
    updated["path"] = form.get("path", updated.get("path", "")).strip()
    updated["patterns"] = _update_patterns_from_form(updated.get("patterns", []), form)
    return updated


def add_pattern(state: dict[str, Any]) -> dict[str, Any]:
    updated = copy.deepcopy(state)
    updated.setdefault("patterns", []).append(_blank_pattern())
    return updated


def remove_pattern(state: dict[str, Any], pattern_id: str) -> dict[str, Any]:
    updated = copy.deepcopy(state)
    updated["patterns"] = [
        pattern for pattern in updated.get("patterns", []) if pattern.get("id") != pattern_id
    ]
    return updated


def patterns_yaml(state: dict[str, Any]) -> str:
    document = {
        "kind": "Patterns",
        "patterns": _document_patterns(state.get("patterns", [])),
    }
    return yaml.safe_dump(document, sort_keys=False, allow_unicode=True)


def save_patterns(config_dir: str, state: dict[str, Any]) -> str:
    relative_path = state.get("path", "").strip()
    if not relative_path:
        raise ValueError("A file path is required")

    path = safe_patterns_path(config_dir, relative_path)
    if path is None:
        raise ValueError("Path must point to a YAML file inside a patterns directory under the selected config path.")

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(patterns_yaml(state))
    return relative_path


def save_uploaded_patterns(token: str, state: dict[str, Any]) -> str:
    relative_path = state.get("path", "").strip()
    if not relative_path:
        raise ValueError("A file path is required")

    if PATTERNS_DIR_NAME not in Path(relative_path).parts:
        raise ValueError("Path must point to a YAML file inside a patterns directory.")

    return save_uploaded_config_text(token, relative_path, patterns_yaml(state))


def _ensure_ids(state: dict[str, Any]) -> dict[str, Any]:
    updated = copy.deepcopy(state)
    updated["patterns"] = [_ensure_pattern_ids(pattern) for pattern in updated.get("patterns", [])]
    return updated


def _ensure_pattern_ids(pattern: dict[str, Any]) -> dict[str, Any]:
    current = copy.deepcopy(pattern)
    current.setdefault("id", uuid.uuid4().hex)
    current.setdefault("name", "")
    current.setdefault("ref", "")
    current.setdefault("pattern_kind", "regex")
    current.setdefault("pattern_text", "")
    current.setdefault("test_includes", "")
    current.setdefault("test_excludes", "")
    return current


def _blank_pattern() -> dict[str, Any]:
    return {
        "id": uuid.uuid4().hex,
        "name": "",
        "ref": "",
        "pattern_kind": "regex",
        "pattern_text": "",
        "test_includes": "",
        "test_excludes": "",
    }


def _patterns_from_document(document_patterns: list[Any]) -> list[dict[str, Any]]:
    patterns: list[dict[str, Any]] = []
    for item in document_patterns:
        if not isinstance(item, dict) or len(item) != 1:
            continue
        name, value = next(iter(item.items()))
        if not isinstance(value, dict):
            continue
        pattern = _blank_pattern()
        pattern["name"] = str(name)
        pattern["ref"] = str(value.get("_ref", ""))
        raw_pattern = value.get("pattern", "")
        if isinstance(raw_pattern, list):
            pattern["pattern_kind"] = "list"
            pattern["pattern_text"] = ", ".join(str(entry) for entry in raw_pattern)
        else:
            pattern["pattern_kind"] = "regex"
            pattern["pattern_text"] = str(raw_pattern)
        includes = value.get("test_includes", [])
        excludes = value.get("test_excludes", [])
        pattern["test_includes"] = ", ".join(str(entry) for entry in includes if str(entry))
        pattern["test_excludes"] = ", ".join(str(entry) for entry in excludes if str(entry))
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
            if pattern.get("pattern_kind") == "list":
                entry["pattern"] = _split_csv(pattern_value)
            else:
                entry["pattern"] = pattern_value
        ref = pattern.get("ref", "").strip()
        if ref:
            entry["_ref"] = ref
        includes = _split_csv(pattern.get("test_includes", ""))
        excludes = _split_csv(pattern.get("test_excludes", ""))
        if includes:
            entry["test_includes"] = includes
        if excludes:
            entry["test_excludes"] = excludes
        document_patterns.append({name: entry})
    return document_patterns


def _update_patterns_from_form(patterns: list[dict[str, Any]], form: Any) -> list[dict[str, Any]]:
    updated: list[dict[str, Any]] = []
    for pattern in patterns:
        pattern_id = pattern["id"]
        current = copy.deepcopy(pattern)
        current["name"] = form.get(f"name-{pattern_id}", current.get("name", "")).strip()
        current["ref"] = form.get(f"ref-{pattern_id}", current.get("ref", "")).strip()
        current["pattern_kind"] = form.get(f"pattern_kind-{pattern_id}", current.get("pattern_kind", "regex"))
        current["pattern_text"] = form.get(f"pattern_text-{pattern_id}", current.get("pattern_text", "")).strip()
        current["test_includes"] = form.get(f"test_includes-{pattern_id}", current.get("test_includes", "")).strip()
        current["test_excludes"] = form.get(f"test_excludes-{pattern_id}", current.get("test_excludes", "")).strip()
        updated.append(current)
    return updated


def _split_csv(value: str) -> list[str]:
    normalized = value.replace("\n", ",")
    return [item.strip() for item in normalized.split(",") if item.strip()]
