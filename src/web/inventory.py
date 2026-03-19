from __future__ import annotations

import copy
import uuid
from typing import Any

import yaml

from src.web.editor_base import BaseEditor, split_csv


ITEM_KEYS = ("_phones", "_flags")


class InventoryEditor(BaseEditor):
    kind = "Inventory"
    dir_name = "inventory"
    collection_key = "nodes"

    def load_state(self, config_dir: str, relative_path: str) -> dict[str, Any]:
        path = self.safe_path(config_dir, relative_path)
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

    def to_yaml(self, state: dict[str, Any]) -> str:
        document = {
            "kind": "Inventory",
            "data": _mapping_from_nodes(state.get("nodes", [])),
        }
        return yaml.safe_dump(document, sort_keys=False, allow_unicode=True)

    def _blank_item(self) -> dict[str, Any]:
        return {
            "id": uuid.uuid4().hex,
            "name": "",
            "ref": "",
            "items_kind": "phones",
            "items_text": "",
            "children": [],
        }

    def _ensure_item_ids(self, item: dict[str, Any]) -> dict[str, Any]:
        current = copy.deepcopy(item)
        current.setdefault("id", uuid.uuid4().hex)
        current.setdefault("name", "")
        current.setdefault("ref", "")
        current.setdefault("items_kind", "phones")
        current.setdefault("items_text", "")
        current["children"] = [
            self._ensure_item_ids(child) for child in current.get("children", [])
        ]
        return current

    def _update_items_from_form(
        self, nodes: list[dict[str, Any]], form: Any
    ) -> list[dict[str, Any]]:
        updated: list[dict[str, Any]] = []
        for node in nodes:
            node_id = node["id"]
            current = copy.deepcopy(node)
            current["name"] = form.get(f"name-{node_id}", current.get("name", "")).strip()
            current["ref"] = form.get(f"ref-{node_id}", current.get("ref", "")).strip()
            current["items_kind"] = form.get(
                f"items_kind-{node_id}", current.get("items_kind", "phones")
            )
            current["items_text"] = form.get(
                f"items_text-{node_id}", current.get("items_text", "")
            ).strip()
            current["children"] = self._update_items_from_form(
                current.get("children", []), form
            )
            if current["children"]:
                current["items_text"] = ""
            updated.append(current)
        return updated

    def remove_item(self, state: dict[str, Any], item_id: str) -> dict[str, Any]:
        updated = copy.deepcopy(state)
        updated["nodes"] = _remove_node(updated.get("nodes", []), item_id)
        return updated

    def add_child_node(self, state: dict[str, Any], node_id: str) -> dict[str, Any]:
        updated = copy.deepcopy(state)
        target = find_node(updated.get("nodes", []), node_id)
        if target is not None:
            target["items_text"] = ""
            target.setdefault("children", []).append(self._blank_item())
        return updated


def find_node(nodes: list[dict[str, Any]], node_id: str) -> dict[str, Any] | None:
    for node in nodes:
        if node.get("id") == node_id:
            return node
        child = find_node(node.get("children", []), node_id)
        if child is not None:
            return child
    return None


def _nodes_from_mapping(mapping: dict[str, Any]) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    for name, value in mapping.items():
        if name.startswith("_") or not isinstance(value, dict):
            continue
        node: dict[str, Any] = {
            "id": uuid.uuid4().hex,
            "name": name,
            "ref": value.get("_ref", ""),
            "items_kind": "phones",
            "items_text": "",
            "children": [],
        }
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
            items = split_csv(node.get("items_text", ""))
            items_kind = node.get("items_kind", "phones")
            if items:
                key = "_flags" if items_kind == "flags" else "_phones"
                entry[key] = items
        mapping[name] = entry
    return mapping


def _remove_node(nodes: list[dict[str, Any]], node_id: str) -> list[dict[str, Any]]:
    remaining: list[dict[str, Any]] = []
    for node in nodes:
        if node.get("id") == node_id:
            continue
        current = copy.deepcopy(node)
        current["children"] = _remove_node(current.get("children", []), node_id)
        remaining.append(current)
    return remaining
