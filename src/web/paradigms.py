from __future__ import annotations

import copy
import uuid
from typing import Any

import yaml

from src.web.editor_base import BaseEditor
from src.web.markers import (
    add_marker_row,
    blank_marker_list,
    ensure_marker_list_ids,
    normalize_marker_list,
    remove_marker_row,
    serialize_marker_list,
    update_marker_list_from_form,
)


def blank_order_stage() -> dict[str, str]:
    return {
        "id": uuid.uuid4().hex,
        "name": "",
    }


def blank_feature_mapping() -> dict[str, str]:
    return {
        "id": uuid.uuid4().hex,
        "feature_name": "",
        "mode": "ref",
        "value": "",
    }


def blank_contingent_marker() -> dict[str, str]:
    return {
        "id": uuid.uuid4().hex,
        "ref": "",
    }


def blank_lexical_feature() -> dict[str, str]:
    return {
        "id": uuid.uuid4().hex,
        "feature_name": "",
        "feature_value": "",
    }


class ParadigmEditor(BaseEditor):
    kind = "Paradigm"
    dir_name = "paradigms"
    collection_key = "feature_mappings"

    def load_state(self, config_dir: str, relative_path: str) -> dict[str, Any]:
        path = self.safe_path(config_dir, relative_path)
        if path is None or not path.exists():
            raise FileNotFoundError(relative_path)

        with path.open("r", encoding="utf-8") as handle:
            document = yaml.safe_load(handle) or {}

        if document.get("kind") != "Paradigm":
            raise ValueError(f"{relative_path} is not a Paradigm config")

        feature_mappings = []
        for feature_name, value in (document.get("feature_markers") or {}).items():
            row = blank_feature_mapping()
            row["feature_name"] = str(feature_name)
            if value is None:
                row["mode"] = "null"
                row["value"] = ""
            else:
                raw_value = str(value)
                row["mode"] = "ref" if raw_value.startswith("$") else "fixed"
                row["value"] = raw_value
            feature_mappings.append(row)

        contingent_markers = []
        for value in document.get("contingent_markers", []) or []:
            row = blank_contingent_marker()
            row["ref"] = str(value or "")
            contingent_markers.append(row)

        order_stages = []
        for value in document.get("order", []) or []:
            row = blank_order_stage()
            row["name"] = str(value or "")
            order_stages.append(row)

        filter_config = document.get("filter") or {}
        filter_lexical_features = []
        for pair in filter_config.get("lexical_features", []) or []:
            row = blank_lexical_feature()
            if isinstance(pair, (list, tuple)) and len(pair) >= 2:
                row["feature_name"] = str(pair[0] or "")
                row["feature_value"] = str(pair[1] or "")
            filter_lexical_features.append(row)

        state = {
            "path": relative_path,
            "kind": "Paradigm",
            "part_of_speech": str(document.get("part_of_speech", "") or ""),
            "order_stages": order_stages,
            "global_markers": normalize_marker_list(document.get("global_markers")),
            "feature_mappings": feature_mappings,
            "feature_combinations": str(document.get("feature_combinations", "") or ""),
            "contingent_markers": contingent_markers,
            "filter_pattern": str(filter_config.get("pattern", "") or ""),
            "filter_lexical_features": filter_lexical_features,
        }
        return state

    def new_state(self, relative_path: str = "") -> dict[str, Any]:
        state = super().new_state(relative_path)
        state["part_of_speech"] = ""
        state["order_stages"] = []
        state["global_markers"] = blank_marker_list()
        state["feature_mappings"] = []
        state["feature_combinations"] = ""
        state["contingent_markers"] = []
        state["filter_pattern"] = ""
        state["filter_lexical_features"] = []
        state["available_part_of_speech"] = []
        state["available_feature_markers"] = []
        state["available_contingent_markers"] = []
        state["available_feature_combinations"] = []
        state["available_features_to_values"] = {}
        state["available_patterns"] = []
        return state

    def state_from_json(self, payload: str | None) -> dict[str, Any]:
        state = super().state_from_json(payload)
        state.setdefault("part_of_speech", "")
        state.setdefault("order_stages", [])
        state.setdefault("feature_combinations", "")
        state.setdefault("contingent_markers", [])
        state.setdefault("filter_pattern", "")
        state.setdefault("filter_lexical_features", [])
        state.setdefault("available_part_of_speech", [])
        state.setdefault("available_feature_markers", [])
        state.setdefault("available_contingent_markers", [])
        state.setdefault("available_feature_combinations", [])
        state.setdefault("available_features_to_values", {})
        state.setdefault("available_patterns", [])
        state["global_markers"] = ensure_marker_list_ids(state.get("global_markers"))
        state["feature_mappings"] = [self._ensure_item_ids(item) for item in state.get("feature_mappings", [])]
        state["order_stages"] = [self._ensure_order_stage_ids(item) for item in state.get("order_stages", [])]
        state["contingent_markers"] = [self._ensure_contingent_ids(item) for item in state.get("contingent_markers", [])]
        state["filter_lexical_features"] = [
            self._ensure_lexical_feature_ids(item)
            for item in state.get("filter_lexical_features", [])
        ]
        return state

    def update_from_form(self, state: dict[str, Any], form: Any) -> dict[str, Any]:
        updated = super().update_from_form(state, form)
        updated["part_of_speech"] = form.get(
            "part_of_speech",
            updated.get("part_of_speech", ""),
        ).strip()
        updated["feature_combinations"] = form.get(
            "feature_combinations",
            updated.get("feature_combinations", ""),
        ).strip()
        updated["filter_pattern"] = form.get(
            "filter_pattern",
            updated.get("filter_pattern", ""),
        ).strip()
        updated["filter_lexical_features"] = self._update_lexical_features_from_form(
            updated.get("filter_lexical_features", []), form
        )
        updated["global_markers"] = update_marker_list_from_form(
            updated.get("global_markers", blank_marker_list()),
            form,
            "global",
        )
        updated["order_stages"] = self._update_order_stages_from_form(
            updated.get("order_stages", []), form
        )
        updated["contingent_markers"] = self._update_contingent_from_form(
            updated.get("contingent_markers", []), form
        )
        return updated

    def to_yaml(self, state: dict[str, Any]) -> str:
        document: dict[str, Any] = {
            "kind": "Paradigm",
            "part_of_speech": state.get("part_of_speech", "").strip(),
        }

        order = [
            item.get("name", "").strip()
            for item in state.get("order_stages", [])
            if item.get("name", "").strip()
        ]
        if order:
            document["order"] = order

        global_markers = serialize_marker_list(state.get("global_markers", {}))
        if global_markers is not None:
            document["global_markers"] = global_markers if isinstance(global_markers, list) else [global_markers]

        feature_markers: dict[str, Any] = {}
        for item in state.get("feature_mappings", []):
            feature_name = item.get("feature_name", "").strip()
            if not feature_name:
                continue
            mode = item.get("mode", "ref")
            value = item.get("value", "").strip()
            if mode == "null":
                feature_markers[feature_name] = None
            elif value:
                feature_markers[feature_name] = value
        document["feature_markers"] = feature_markers

        feature_combinations = state.get("feature_combinations", "").strip()
        if feature_combinations:
            document["feature_combinations"] = feature_combinations

        contingent_markers = [
            item.get("ref", "").strip()
            for item in state.get("contingent_markers", [])
            if item.get("ref", "").strip()
        ]
        if contingent_markers:
            document["contingent_markers"] = contingent_markers

        filter_data: dict[str, Any] = {}
        lf_pairs = [
            [item.get("feature_name", "").strip(), item.get("feature_value", "").strip()]
            for item in state.get("filter_lexical_features", [])
            if item.get("feature_name", "").strip() and item.get("feature_value", "").strip()
        ]
        if lf_pairs:
            filter_data["lexical_features"] = lf_pairs
        pattern = state.get("filter_pattern", "").strip()
        if pattern:
            filter_data["pattern"] = pattern
        if filter_data:
            document["filter"] = filter_data

        return yaml.safe_dump(document, sort_keys=False, allow_unicode=True)

    def _blank_item(self) -> dict[str, Any]:
        return blank_feature_mapping()

    def _ensure_item_ids(self, item: dict[str, Any]) -> dict[str, Any]:
        current = copy.deepcopy(item or {})
        defaults = blank_feature_mapping()
        for key, value in defaults.items():
            current.setdefault(key, value)
        return current

    def _ensure_order_stage_ids(self, item: dict[str, Any]) -> dict[str, Any]:
        current = copy.deepcopy(item or {})
        defaults = blank_order_stage()
        for key, value in defaults.items():
            current.setdefault(key, value)
        return current

    def _ensure_contingent_ids(self, item: dict[str, Any]) -> dict[str, Any]:
        current = copy.deepcopy(item or {})
        defaults = blank_contingent_marker()
        for key, value in defaults.items():
            current.setdefault(key, value)
        return current

    def _update_items_from_form(
        self, items: list[dict[str, Any]], form: Any
    ) -> list[dict[str, Any]]:
        updated: list[dict[str, Any]] = []
        for item in items:
            row_id = item["id"]
            current = self._ensure_item_ids(item)
            current["feature_name"] = form.get(
                f"feature-name-{row_id}",
                current.get("feature_name", ""),
            ).strip()
            current["mode"] = form.get(
                f"feature-mode-{row_id}",
                current.get("mode", "ref"),
            ).strip() or "ref"
            current["value"] = form.get(
                f"feature-value-{row_id}",
                current.get("value", ""),
            ).strip()
            updated.append(current)
        return updated

    def _update_order_stages_from_form(
        self, items: list[dict[str, Any]], form: Any
    ) -> list[dict[str, Any]]:
        updated = []
        for item in items:
            row_id = item["id"]
            current = self._ensure_order_stage_ids(item)
            current["name"] = form.get(
                f"order-name-{row_id}",
                current.get("name", ""),
            ).strip()
            updated.append(current)
        return updated

    def _update_contingent_from_form(
        self, items: list[dict[str, Any]], form: Any
    ) -> list[dict[str, Any]]:
        updated = []
        for item in items:
            row_id = item["id"]
            current = self._ensure_contingent_ids(item)
            current["ref"] = form.get(
                f"contingent-ref-{row_id}",
                current.get("ref", ""),
            ).strip()
            updated.append(current)
        return updated

    def _ensure_lexical_feature_ids(self, item: dict[str, Any]) -> dict[str, Any]:
        current = copy.deepcopy(item or {})
        for key, value in blank_lexical_feature().items():
            current.setdefault(key, value)
        return current

    def _update_lexical_features_from_form(
        self, items: list[dict[str, Any]], form: Any
    ) -> list[dict[str, Any]]:
        updated = []
        for item in items:
            row_id = item["id"]
            current = self._ensure_lexical_feature_ids(item)
            current["feature_name"] = form.get(f"lf-name-{row_id}", "").strip()
            current["feature_value"] = form.get(f"lf-value-{row_id}", "").strip()
            updated.append(current)
        return updated

    def add_lexical_feature(self, state: dict[str, Any]) -> dict[str, Any]:
        updated = copy.deepcopy(state)
        updated.setdefault("filter_lexical_features", []).append(blank_lexical_feature())
        return updated

    def remove_lexical_feature(self, state: dict[str, Any], feature_id: str) -> dict[str, Any]:
        updated = copy.deepcopy(state)
        updated["filter_lexical_features"] = [
            item for item in updated.get("filter_lexical_features", [])
            if item.get("id") != feature_id
        ]
        return updated

    def add_order_stage(self, state: dict[str, Any]) -> dict[str, Any]:
        updated = copy.deepcopy(state)
        updated.setdefault("order_stages", []).append(blank_order_stage())
        return updated

    def remove_order_stage(self, state: dict[str, Any], stage_id: str) -> dict[str, Any]:
        updated = copy.deepcopy(state)
        updated["order_stages"] = [
            item for item in updated.get("order_stages", [])
            if item.get("id") != stage_id
        ]
        return updated

    def add_global_marker(self, state: dict[str, Any]) -> dict[str, Any]:
        updated = copy.deepcopy(state)
        updated["global_markers"] = add_marker_row(
            updated.get("global_markers", blank_marker_list())
        )
        return updated

    def remove_marker(self, state: dict[str, Any], marker_id: str) -> dict[str, Any]:
        updated = copy.deepcopy(state)
        updated["global_markers"] = remove_marker_row(
            updated.get("global_markers", blank_marker_list()),
            marker_id,
        )
        return updated

    def add_contingent_marker(self, state: dict[str, Any]) -> dict[str, Any]:
        updated = copy.deepcopy(state)
        updated.setdefault("contingent_markers", []).append(blank_contingent_marker())
        return updated

    def remove_contingent_marker(self, state: dict[str, Any], marker_id: str) -> dict[str, Any]:
        updated = copy.deepcopy(state)
        updated["contingent_markers"] = [
            item for item in updated.get("contingent_markers", [])
            if item.get("id") != marker_id
        ]
        return updated

    def _run_test(self, item: dict[str, Any], registry: Any) -> dict:
        raise NotImplementedError("Paradigm does not support testing")
