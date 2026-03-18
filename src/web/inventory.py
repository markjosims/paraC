from __future__ import annotations

import copy
import json
import uuid
from pathlib import Path
from typing import Any

import yaml

from src.web.configs import (
    load_uploaded_config_entry,
    save_uploaded_config_text,
    safe_file_path,
)


INVENTORY_DIR_NAME = "inventory"
ITEM_KEYS = ("_phones", "_flags")


def safe_inventory_path(config_dir: str, relative_path: str) -> Path | None:
    path = safe_file_path(config_dir, relative_path)
    if path is None:
        return None
    if INVENTORY_DIR_NAME not in path.parts:
        return None
    return path


def new_inventory_state(relative_path: str = "") -> dict[str, Any]:
    return {
        "path": relative_path,
        "kind": "Inventory",
        "nodes": [],
    }


def load_inventory_state(config_dir: str, relative_path: str) -> dict[str, Any]:
    path = safe_inventory_path(config_dir, relative_path)
    if path is None or not path.exists():
        raise FileNotFoundError(relative_path)

    with path.open("r", encoding="utf-8") as handle:
        document = yaml.safe_load(handle) or {}

    if document.get("kind") != "Inventory":
        raise ValueError(f"{relative_path} is not an Inventory config")

    return {
        "path": relative_path,
        "kind": "Inventory",
        "nodes": _nodes_from_mapping(document.get("data", {})),
    }


def state_from_json(payload: str | None) -> dict[str, Any]:
    if not payload:
        return new_inventory_state()
    state = json.loads(payload)
    state.setdefault("kind", "Inventory")
    state.setdefault("path", "")
    state.setdefault("nodes", [])
    return _ensure_ids(state)


def state_to_json(state: dict[str, Any]) -> str:
    return json.dumps(state, ensure_ascii=False)


def update_state_from_form(state: dict[str, Any], form: Any) -> dict[str, Any]:
    updated = copy.deepcopy(state)
    updated["path"] = form.get("path", updated.get("path", "")).strip()
    updated["nodes"] = _update_nodes_from_form(updated.get("nodes", []), form)
    return updated


def add_root_node(state: dict[str, Any]) -> dict[str, Any]:
    updated = copy.deepcopy(state)
    updated.setdefault("nodes", []).append(_blank_node())
    return updated


def add_child_node(state: dict[str, Any], node_id: str) -> dict[str, Any]:
    updated = copy.deepcopy(state)
    target = find_node(updated.get("nodes", []), node_id)
    if target is not None:
        target["items_text"] = ""
        target.setdefault("children", []).append(_blank_node())
    return updated


def remove_node(state: dict[str, Any], node_id: str) -> dict[str, Any]:
    updated = copy.deepcopy(state)
    updated["nodes"] = _remove_node(updated.get("nodes", []), node_id)
    return updated


def inventory_yaml(state: dict[str, Any]) -> str:
    document = {
        "kind": "Inventory",
        "data": _mapping_from_nodes(state.get("nodes", [])),
    }
    return yaml.safe_dump(document, sort_keys=False, allow_unicode=True)


def save_inventory(config_dir: str, state: dict[str, Any]) -> str:
    relative_path = state.get("path", "").strip()
    if not relative_path:
        raise ValueError("A file path is required")

    path = safe_inventory_path(config_dir, relative_path)
    if path is None:
        raise ValueError("Path must point to a YAML file inside an inventory directory under the selected config path.")

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(inventory_yaml(state))
    return relative_path


def suggested_inventory_path(file_stem: str) -> str:
    safe_stem = file_stem.strip().replace(" ", "_")
    if not safe_stem:
        return ""
    return f"{INVENTORY_DIR_NAME}/{safe_stem}.yaml"


def load_uploaded_inventory_state(token: str, relative_path: str) -> dict[str, Any]:
    document = load_uploaded_config_entry(token, relative_path)["parsed"]
    if not isinstance(document, dict) or document.get("kind") != "Inventory":
        raise ValueError(f"{relative_path} is not an Inventory config")

    return {
        "path": relative_path,
        "kind": "Inventory",
        "nodes": _nodes_from_mapping(document.get("data", {})),
    }


def save_uploaded_inventory(token: str, state: dict[str, Any]) -> str:
    relative_path = state.get("path", "").strip()
    if not relative_path:
        raise ValueError("A file path is required")

    if INVENTORY_DIR_NAME not in Path(relative_path).parts:
        raise ValueError("Path must point to a YAML file inside an inventory directory.")

    return save_uploaded_config_text(token, relative_path, inventory_yaml(state))


def find_node(nodes: list[dict[str, Any]], node_id: str) -> dict[str, Any] | None:
    for node in nodes:
        if node.get("id") == node_id:
            return node
        child = find_node(node.get("children", []), node_id)
        if child is not None:
            return child
    return None


def _ensure_ids(state: dict[str, Any]) -> dict[str, Any]:
    state = copy.deepcopy(state)
    state["nodes"] = [_ensure_node_ids(node) for node in state.get("nodes", [])]
    return state


def _ensure_node_ids(node: dict[str, Any]) -> dict[str, Any]:
    current = copy.deepcopy(node)
    current.setdefault("id", uuid.uuid4().hex)
    current.setdefault("name", "")
    current.setdefault("ref", "")
    current.setdefault("items_kind", "phones")
    current.setdefault("items_text", "")
    current["children"] = [_ensure_node_ids(child) for child in current.get("children", [])]
    return current


def _blank_node() -> dict[str, Any]:
    return {
        "id": uuid.uuid4().hex,
        "name": "",
        "ref": "",
        "items_kind": "phones",
        "items_text": "",
        "children": [],
    }


def _nodes_from_mapping(mapping: dict[str, Any]) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    for name, value in mapping.items():
        if name.startswith("_") or not isinstance(value, dict):
            continue
        node = _blank_node()
        node["name"] = name
        node["ref"] = value.get("_ref", "")
        child_mapping = {
            child_name: child_value
            for child_name, child_value in value.items()
            if not child_name.startswith("_")
        }
        for key in ITEM_KEYS:
            if key in value and not child_mapping:
                node["items_kind"] = "phones" if key == "_phones" else "flags"
                node["items_text"] = ", ".join(str(item) for item in value.get(key, []))
                break
        node["children"] = _nodes_from_mapping(child_mapping)
        nodes.append(node)
    return nodes


def _mapping_from_nodes(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    mapping: dict[str, Any] = {}
    for node in nodes:
        name = node.get("name", "").strip()
        if not name:
            continue

        entry: dict[str, Any] = {}
        ref = node.get("ref", "").strip()
        if ref:
            entry["_ref"] = ref

        child_mapping = _mapping_from_nodes(node.get("children", []))
        if child_mapping:
            entry.update(child_mapping)
        else:
            items = _split_items(node.get("items_text", ""))
            items_kind = node.get("items_kind", "phones")
            if items:
                key = "_flags" if items_kind == "flags" else "_phones"
                entry[key] = items
        mapping[name] = entry
    return mapping


def _update_nodes_from_form(nodes: list[dict[str, Any]], form: Any) -> list[dict[str, Any]]:
    updated: list[dict[str, Any]] = []
    for node in nodes:
        node_id = node["id"]
        current = copy.deepcopy(node)
        current["name"] = form.get(f"name-{node_id}", current.get("name", "")).strip()
        current["ref"] = form.get(f"ref-{node_id}", current.get("ref", "")).strip()
        current["items_kind"] = form.get(f"items_kind-{node_id}", current.get("items_kind", "phones"))
        current["items_text"] = form.get(f"items_text-{node_id}", current.get("items_text", "")).strip()
        current["children"] = _update_nodes_from_form(current.get("children", []), form)
        if current["children"]:
            current["items_text"] = ""
        updated.append(current)
    return updated


def _remove_node(nodes: list[dict[str, Any]], node_id: str) -> list[dict[str, Any]]:
    remaining: list[dict[str, Any]] = []
    for node in nodes:
        if node.get("id") == node_id:
            continue
        current = copy.deepcopy(node)
        current["children"] = _remove_node(current.get("children", []), node_id)
        remaining.append(current)
    return remaining


def _split_items(value: str) -> list[str]:
    normalized = value.replace("\n", ",")
    return [item.strip() for item in normalized.split(",") if item.strip()]
