from __future__ import annotations

import json
import secrets
import shutil
import tempfile
from pathlib import Path
from typing import Any

import yaml

from src.constants import PROJECT_ROOT


KIND_DIRECTORY_NAMES = {
    "Inventory": "inventory",
    "Patterns": "patterns",
    "Rule": "rules",
    "Feature": "features",
    "Marker": "markers",
    "Paradigm": "paradigms",
    "PartOfSpeech": "parts_of_speech",
}
PREFERRED_KIND_ORDER = tuple(KIND_DIRECTORY_NAMES)
UPLOAD_SESSIONS: dict[str, dict[str, Any]] = {}


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
    root = normalize_config_dir(config_dir)
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
    root = normalize_config_dir(config_dir)
    if root is None:
        return []

    files: list[dict[str, str]] = []
    for path in sorted(root.rglob("*.y*ml")):
        relative_path = str(path.relative_to(root))
        files.append(_entry_from_content(relative_path, path.read_text(encoding="utf-8")))
    return files


def detect_yaml_kind(config_dir: str, relative_path: str) -> str | None:
    entry = load_config_entry(config_dir, relative_path)
    return entry.get("kind") or None


def load_config_entry(config_dir: str, relative_path: str) -> dict[str, Any]:
    path = safe_file_path(config_dir, relative_path)
    if path is None or not path.exists():
        raise FileNotFoundError(relative_path)
    return _entry_from_content(relative_path, path.read_text(encoding="utf-8"))


def save_config_text(config_dir: str, relative_path: str, content: str) -> str:
    if not relative_path.strip():
        raise ValueError("A file path is required")

    path = safe_file_path(config_dir, relative_path)
    if path is None:
        raise ValueError("Path must point to a YAML file inside the selected config directory.")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return relative_path


def create_manifest_session(payload: str) -> str:
    manifest = json.loads(payload)
    token = secrets.token_urlsafe(16)
    entries: dict[str, dict[str, Any]] = {}
    for item in manifest.get("files", []):
        relative_path = str(item.get("path", "")).strip()
        if not relative_path.endswith((".yaml", ".yml")):
            continue
        content = str(item.get("content", ""))
        entries[relative_path] = _entry_from_content(relative_path, content)

    UPLOAD_SESSIONS[token] = {
        "label": str(manifest.get("label") or _session_label(entries)),
        "files": entries,
    }
    return token


def get_upload_session(token: str) -> dict[str, Any] | None:
    return UPLOAD_SESSIONS.get(token)


def materialize_upload_session(token: str) -> Path:
    session = get_upload_session(token)
    if not session:
        raise ValueError("Upload session not found.")

    root = Path(tempfile.gettempdir()) / "parser_tira_uploads" / token
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)

    for relative_path, entry in session["files"].items():
        path = (root / relative_path).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"Invalid uploaded path: {relative_path}") from exc
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(entry.get("content", ""), encoding="utf-8")

    return root


def list_uploaded_yaml_files(token: str) -> list[dict[str, str]]:
    session = get_upload_session(token)
    if not session:
        return []
    return [session["files"][path] for path in sorted(session["files"])]


def detect_uploaded_yaml_kind(token: str, relative_path: str) -> str | None:
    try:
        entry = load_uploaded_config_entry(token, relative_path)
    except FileNotFoundError:
        return None
    kind = entry.get("kind")
    return kind if isinstance(kind, str) and kind else None


def load_uploaded_config_entry(token: str, relative_path: str) -> dict[str, Any]:
    session = get_upload_session(token)
    if not session or relative_path not in session["files"]:
        raise FileNotFoundError(relative_path)
    return session["files"][relative_path]


def save_uploaded_config_text(token: str, relative_path: str, content: str) -> str:
    session = get_upload_session(token)
    if not session:
        raise ValueError("Upload session not found.")
    if not relative_path.strip():
        raise ValueError("A file path is required")

    session["files"][relative_path] = _entry_from_content(relative_path, content)
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


def _session_label(entries: dict[str, dict[str, Any]]) -> str:
    if not entries:
        return "Uploaded directory"
    first_path = next(iter(sorted(entries)))
    first_parts = Path(first_path).parts
    if first_parts:
        return first_parts[0]
    return "Uploaded directory"
