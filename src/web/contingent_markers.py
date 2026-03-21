from __future__ import annotations

import copy
from typing import Any

import yaml

from src.web.editor_base import BaseEditor
from src.web.markers import (
    add_marker_row,
    blank_inner_entry,
    blank_marker_list,
    blank_outer_entry,
    ensure_marker_list_ids,
    normalize_marker_list,
    remove_marker_row,
    serialize_marker_list,
    update_marker_list_from_form,
)


class ContingentFeatureMarkersEditor(BaseEditor):
    kind = "ContingentFeatureMarkers"
    dir_name = "markers"
    collection_key = "outer_entries"

    def load_state(self, config_dir: str, relative_path: str) -> dict[str, Any]:
        path = self.safe_path(config_dir, relative_path)
        if path is None or not path.exists():
            raise FileNotFoundError(relative_path)

        with path.open("r", encoding="utf-8") as handle:
            document = yaml.safe_load(handle) or {}

        if document.get("kind") != "ContingentFeatureMarkers":
            raise ValueError(
                f"{relative_path} is not a ContingentFeatureMarkers config"
            )

        outer_entries = []
        for outer_config in document.get("markers", []) or []:
            outer_entry = blank_outer_entry()
            outer_entry["outer_feature_value"] = str(
                outer_config.get("outer_feature_value", "") or ""
            )
            inner_entries = []
            for inner_value, marker_config in (
                outer_config.get("inner_feature_values") or {}
            ).items():
                inner_entry = blank_inner_entry()
                inner_entry["inner_feature_value"] = str(inner_value)
                inner_entry["marker_list"] = normalize_marker_list(marker_config)
                inner_entries.append(inner_entry)
            outer_entry["inner_entries"] = inner_entries or [blank_inner_entry()]
            outer_entries.append(outer_entry)

        return {
            "path": relative_path,
            "kind": "ContingentFeatureMarkers",
            "outer_feature": str(document.get("outer_feature", "") or ""),
            "inner_feature": str(document.get("inner_feature", "") or ""),
            "global_order": str(document.get("global_order", "") or ""),
            "global_markers": normalize_marker_list(document.get("global_markers")),
            "outer_entries": outer_entries,
        }

    def new_state(self, relative_path: str = "") -> dict[str, Any]:
        state = super().new_state(relative_path)
        state["outer_feature"] = ""
        state["inner_feature"] = ""
        state["global_order"] = ""
        state["global_markers"] = blank_marker_list()
        return state

    def state_from_json(self, payload: str | None) -> dict[str, Any]:
        state = super().state_from_json(payload)
        state.setdefault("outer_feature", "")
        state.setdefault("inner_feature", "")
        state.setdefault("global_order", "")
        state["global_markers"] = ensure_marker_list_ids(
            state.get("global_markers")
        )
        state["outer_entries"] = [
            self._ensure_item_ids(item) for item in state.get("outer_entries", [])
        ]
        return state

    def update_from_form(self, state: dict[str, Any], form: Any) -> dict[str, Any]:
        updated = super().update_from_form(state, form)
        updated["outer_feature"] = form.get(
            "outer_feature",
            updated.get("outer_feature", ""),
        ).strip()
        updated["inner_feature"] = form.get(
            "inner_feature",
            updated.get("inner_feature", ""),
        ).strip()
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
            "kind": "ContingentFeatureMarkers",
            "outer_feature": state.get("outer_feature", "").strip(),
            "inner_feature": state.get("inner_feature", "").strip(),
        }

        global_order = state.get("global_order", "").strip()
        if global_order:
            document["global_order"] = global_order

        global_markers = serialize_marker_list(state.get("global_markers", {}))
        if global_markers is not None:
            document["global_markers"] = global_markers

        markers = []
        for outer_entry in state.get("outer_entries", []):
            outer_value = outer_entry.get("outer_feature_value", "").strip()
            if not outer_value:
                continue

            inner_feature_values: dict[str, Any] = {}
            for inner_entry in outer_entry.get("inner_entries", []):
                inner_value = inner_entry.get("inner_feature_value", "").strip()
                if not inner_value:
                    continue
                inner_feature_values[inner_value] = serialize_marker_list(
                    inner_entry.get("marker_list", {})
                )

            markers.append({
                "outer_feature_value": outer_value,
                "inner_feature_values": inner_feature_values,
            })

        document["markers"] = markers
        return yaml.safe_dump(document, sort_keys=False, allow_unicode=True)

    def _blank_item(self) -> dict[str, Any]:
        return blank_outer_entry()

    def _ensure_item_ids(self, item: dict[str, Any]) -> dict[str, Any]:
        current = copy.deepcopy(item or {})
        defaults = blank_outer_entry()
        for key, value in defaults.items():
            current.setdefault(key, value)
        current["inner_entries"] = [
            self._ensure_inner_entry_ids(inner)
            for inner in current.get("inner_entries", [])
        ] or [blank_inner_entry()]
        return current

    def _ensure_inner_entry_ids(self, item: dict[str, Any]) -> dict[str, Any]:
        current = copy.deepcopy(item or {})
        defaults = blank_inner_entry()
        for key, value in defaults.items():
            current.setdefault(key, value)
        current["marker_list"] = ensure_marker_list_ids(current.get("marker_list"))
        return current

    def _update_items_from_form(
        self, items: list[dict[str, Any]], form: Any
    ) -> list[dict[str, Any]]:
        updated: list[dict[str, Any]] = []
        for item in items:
            outer_id = item["id"]
            current = self._ensure_item_ids(item)
            current["outer_feature_value"] = form.get(
                f"outer-value-{outer_id}",
                current.get("outer_feature_value", ""),
            ).strip()

            inner_entries = []
            for inner in current.get("inner_entries", []):
                inner_id = inner["id"]
                inner_current = self._ensure_inner_entry_ids(inner)
                inner_current["inner_feature_value"] = form.get(
                    f"inner-value-{inner_id}",
                    inner_current.get("inner_feature_value", ""),
                ).strip()
                inner_current["marker_list"] = update_marker_list_from_form(
                    inner_current.get("marker_list", blank_marker_list()),
                    form,
                    f"inner-{inner_id}",
                )
                inner_entries.append(inner_current)
            current["inner_entries"] = inner_entries
            updated.append(current)
        return updated

    def add_global_marker(self, state: dict[str, Any]) -> dict[str, Any]:
        updated = copy.deepcopy(state)
        updated["global_markers"] = add_marker_row(
            updated.get("global_markers", blank_marker_list())
        )
        return updated

    def add_inner_entry(self, state: dict[str, Any], outer_id: str) -> dict[str, Any]:
        updated = copy.deepcopy(state)
        for outer in updated.get("outer_entries", []):
            if outer.get("id") == outer_id:
                outer.setdefault("inner_entries", []).append(blank_inner_entry())
                break
        return updated

    def remove_inner_entry(self, state: dict[str, Any], inner_id: str) -> dict[str, Any]:
        updated = copy.deepcopy(state)
        for outer in updated.get("outer_entries", []):
            outer["inner_entries"] = [
                inner for inner in outer.get("inner_entries", [])
                if inner.get("id") != inner_id
            ] or [blank_inner_entry()]
        return updated

    def add_inner_marker(self, state: dict[str, Any], inner_id: str) -> dict[str, Any]:
        updated = copy.deepcopy(state)
        for outer in updated.get("outer_entries", []):
            for inner in outer.get("inner_entries", []):
                if inner.get("id") == inner_id:
                    inner["marker_list"] = add_marker_row(
                        inner.get("marker_list", blank_marker_list())
                    )
                    return updated
        return updated

    def remove_marker(self, state: dict[str, Any], marker_id: str) -> dict[str, Any]:
        updated = copy.deepcopy(state)
        updated["global_markers"] = remove_marker_row(
            updated.get("global_markers", blank_marker_list()),
            marker_id,
        )
        for outer in updated.get("outer_entries", []):
            for inner in outer.get("inner_entries", []):
                inner["marker_list"] = remove_marker_row(
                    inner.get("marker_list", blank_marker_list()),
                    marker_id,
                )
        return updated

    def _run_test(self, item: dict[str, Any], registry: Any) -> dict:
        raise NotImplementedError(
            "ContingentFeatureMarkers does not support testing"
        )
