from __future__ import annotations

import copy
from typing import Any

import yaml

from src.web.editor_base import BaseEditor
from src.web.markers import (
    add_marker_row,
    blank_feature_entry,
    blank_marker_list,
    ensure_marker_list_ids,
    normalize_marker_list,
    remove_marker_row,
    serialize_marker_list,
    update_marker_list_from_form,
)


class FeatureMarkersEditor(BaseEditor):
    kind = "FeatureMarkers"
    dir_name = "markers"
    collection_key = "entries"

    def load_state(self, config_dir: str, relative_path: str) -> dict[str, Any]:
        path = self.safe_path(config_dir, relative_path)
        if path is None or not path.exists():
            raise FileNotFoundError(relative_path)

        with path.open("r", encoding="utf-8") as handle:
            document = yaml.safe_load(handle) or {}

        if document.get("kind") != "FeatureMarkers":
            raise ValueError(f"{relative_path} is not a FeatureMarkers config")

        entries = []
        for feature_value, marker_config in (document.get("markers") or {}).items():
            entry = blank_feature_entry()
            entry["feature_value"] = str(feature_value)
            entry["marker_list"] = normalize_marker_list(marker_config)
            entries.append(entry)

        return {
            "path": relative_path,
            "kind": "FeatureMarkers",
            "feature": str(document.get("feature", "") or ""),
            "global_order": str(document.get("global_order", "") or ""),
            "global_markers": normalize_marker_list(document.get("global_markers")),
            "entries": entries,
        }

    def new_state(self, relative_path: str = "") -> dict[str, Any]:
        state = super().new_state(relative_path)
        state["feature"] = ""
        state["global_order"] = ""
        state["global_markers"] = blank_marker_list()
        return state

    def state_from_json(self, payload: str | None) -> dict[str, Any]:
        state = super().state_from_json(payload)
        state.setdefault("feature", "")
        state.setdefault("global_order", "")
        state["global_markers"] = ensure_marker_list_ids(
            state.get("global_markers")
        )
        state["entries"] = [self._ensure_item_ids(item) for item in state.get("entries", [])]
        return state

    def update_from_form(self, state: dict[str, Any], form: Any) -> dict[str, Any]:
        updated = super().update_from_form(state, form)
        updated["feature"] = form.get("feature", updated.get("feature", "")).strip()
        updated["global_order"] = form.get(
            "global_order",
            updated.get("global_order", ""),
        ).strip()
        updated["global_markers"] = update_marker_list_from_form(
            updated.get("global_markers", blank_marker_list()),
            form,
            "global",
        )
        return updated

    def to_yaml(self, state: dict[str, Any]) -> str:
        document: dict[str, Any] = {
            "kind": "FeatureMarkers",
            "feature": state.get("feature", "").strip(),
        }

        global_order = state.get("global_order", "").strip()
        if global_order:
            document["global_order"] = global_order

        global_markers = serialize_marker_list(state.get("global_markers", {}))
        if global_markers is not None:
            document["global_markers"] = global_markers

        markers: dict[str, Any] = {}
        for entry in state.get("entries", []):
            feature_value = entry.get("feature_value", "").strip()
            if not feature_value:
                continue
            markers[feature_value] = serialize_marker_list(entry.get("marker_list", {}))
        document["markers"] = markers

        return yaml.safe_dump(document, sort_keys=False, allow_unicode=True)

    def _blank_item(self) -> dict[str, Any]:
        return blank_feature_entry()

    def _ensure_item_ids(self, item: dict[str, Any]) -> dict[str, Any]:
        current = copy.deepcopy(item or {})
        defaults = blank_feature_entry()
        for key, value in defaults.items():
            current.setdefault(key, value)
        current["marker_list"] = ensure_marker_list_ids(current.get("marker_list"))
        return current

    def _update_items_from_form(
        self, items: list[dict[str, Any]], form: Any
    ) -> list[dict[str, Any]]:
        updated: list[dict[str, Any]] = []
        for item in items:
            entry_id = item["id"]
            current = self._ensure_item_ids(item)
            current["feature_value"] = form.get(
                f"feature-value-{entry_id}",
                current.get("feature_value", ""),
            ).strip()
            current["marker_list"] = update_marker_list_from_form(
                current.get("marker_list", blank_marker_list()),
                form,
                f"entry-{entry_id}",
            )
            updated.append(current)
        return updated

    def add_global_marker(self, state: dict[str, Any]) -> dict[str, Any]:
        updated = copy.deepcopy(state)
        updated["global_markers"] = add_marker_row(
            updated.get("global_markers", blank_marker_list())
        )
        return updated

    def add_entry_marker(self, state: dict[str, Any], entry_id: str) -> dict[str, Any]:
        updated = copy.deepcopy(state)
        for entry in updated.get("entries", []):
            if entry.get("id") == entry_id:
                entry["marker_list"] = add_marker_row(
                    entry.get("marker_list", blank_marker_list())
                )
                break
        return updated

    def remove_marker(self, state: dict[str, Any], marker_id: str) -> dict[str, Any]:
        updated = copy.deepcopy(state)
        updated["global_markers"] = remove_marker_row(
            updated.get("global_markers", blank_marker_list()),
            marker_id,
        )
        for entry in updated.get("entries", []):
            entry["marker_list"] = remove_marker_row(
                entry.get("marker_list", blank_marker_list()),
                marker_id,
            )
        return updated

    def _run_test(self, item: dict[str, Any], registry: Any) -> dict:
        raise NotImplementedError("FeatureMarkers does not support testing")
