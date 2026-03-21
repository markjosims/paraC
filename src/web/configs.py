from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.constants import PROJECT_ROOT


KIND_DIRECTORY_NAMES = {
    "Inventory": "inventory",
    "Patterns": "patterns",
    "Rule": "rules",
    "Feature": "features",
    "FeatureDefinitions": "features",
    "FeatureCombinations": "features",
    "Marker": "markers",
    "FeatureMarkers": "markers",
    "ContingentFeatureMarkers": "markers",
    "Paradigm": "paradigms",
    "PartOfSpeech": "parts_of_speech",
}
PREFERRED_KIND_ORDER = tuple(KIND_DIRECTORY_NAMES)


def normalize_config_dir(config_dir: str) -> Path | None:
    if not config_dir.strip():
        return None
    raw_path = Path(config_dir).expanduser()
    if not raw_path.is_absolute():
        raw_path = Path(PROJECT_ROOT) / raw_path
    resolved = raw_path.resolve()
    if not resolved.exists() or not resolved.is_dir():
        return None
    return resolved


def safe_file_path(config_dir: str, relative_path: str) -> Path | None:
    root = _config_root(config_dir)
    if root is None:
        return None
    path = (root / relative_path).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return None
    if path.suffix not in {".yaml", ".yml"}:
        return None
    return path


def list_config_yaml_files(config_dir: str) -> list[dict[str, str]]:
    root = _config_root(config_dir)
    return [_load_entry_from_path(root, path) for path in _yaml_paths(root)]


def detect_yaml_kind(config_dir: str, relative_path: str) -> str | None:
    entry = load_config_entry(config_dir, relative_path)
    return entry.get("kind") or None


def load_config_entry(config_dir: str, relative_path: str) -> dict[str, Any]:
    root = _config_root(config_dir)
    path = safe_file_path(config_dir, relative_path)
    if root is None or path is None or not path.exists():
        raise FileNotFoundError(relative_path)
    return _load_entry_from_path(root, path)


def save_config_text(config_dir: str, relative_path: str, content: str) -> str:
    if not relative_path.strip():
        raise ValueError("A file path is required")

    path = safe_file_path(config_dir, relative_path)
    if path is None:
        raise ValueError("Path must point to a YAML file inside the selected config directory.")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return relative_path


def group_yaml_files_by_kind(yaml_files: list[dict[str, str]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for item in yaml_files:
        kind = item.get("kind") or "Unknown"
        grouped.setdefault(kind, []).append(item)

    ordered_kinds = [
        kind for kind in PREFERRED_KIND_ORDER if grouped.get(kind)
    ]
    ordered_kinds.extend(
        sorted(kind for kind in grouped if kind not in PREFERRED_KIND_ORDER and kind != "Unknown")
    )
    if grouped.get("Unknown"):
        ordered_kinds.append("Unknown")

    yaml_groups = [
        {
            "kind": kind,
            "slug": kind.lower().replace(" ", "-"),
            "dom_id": f"config-group-{kind.lower().replace(' ', '-')}",
            "count": len(grouped[kind]),
            "config_items": grouped[kind],
        }
        for kind in ordered_kinds
    ]
    return yaml_groups


def known_config_kinds(yaml_files: list[dict[str, str]]) -> list[str]:
    discovered = {item.get("kind") for item in yaml_files if item.get("kind")}
    kinds = [kind for kind in PREFERRED_KIND_ORDER if kind in discovered]
    kinds.extend(sorted(kind for kind in discovered if kind not in PREFERRED_KIND_ORDER))
    return kinds or list(PREFERRED_KIND_ORDER)


def suggested_config_path(kind: str, file_stem: str) -> str:
    safe_stem = file_stem.strip().replace(" ", "_")
    if not safe_stem:
        return ""
    directory = KIND_DIRECTORY_NAMES.get(kind)
    if not directory:
        return f"{safe_stem}.yaml"
    return f"{directory}/{safe_stem}.yaml"


def new_text_config_state(kind: str = "", relative_path: str = "") -> dict[str, str]:
    return {
        "path": relative_path,
        "kind": kind,
        "content": _default_content(kind),
    }


def _default_content(kind: str) -> str:
    if not kind:
        return ""
    return f"kind: {kind}\n"


def _config_root(config_dir: str) -> Path | None:
    return normalize_config_dir(config_dir)


def _yaml_paths(root: Path | None) -> list[Path]:
    if root is None:
        return []
    return sorted(path for path in root.rglob("*") if path.is_file() and path.suffix in {".yaml", ".yml"})


def _load_entry_from_path(root: Path, path: Path) -> dict[str, Any]:
    relative_path = str(path.relative_to(root))
    return _entry_from_content(relative_path, path.read_text(encoding="utf-8"))


def _entry_from_content(relative_path: str, content: str) -> dict[str, Any]:
    try:
        parsed = yaml.safe_load(content) or {}
    except yaml.YAMLError:
        parsed = {}
    kind = parsed.get("kind") if isinstance(parsed, dict) else ""
    stem = Path(relative_path).stem
    return {
        "label": stem,
        "path": relative_path,
        "content": content,
        "parsed": parsed if isinstance(parsed, dict) else {},
        "kind": kind if isinstance(kind, str) else "",
    }
