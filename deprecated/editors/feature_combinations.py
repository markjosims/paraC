from __future__ import annotations

import copy
import uuid
from typing import Any

import yaml

from src.editors.editor_base import BaseEditor, split_csv


class FeatureCombinationsEditor(BaseEditor):
    kind = "FeatureCombinations"
    dir_name = "features"
    collection_key = "combinations"

    def load_state(self, config_dir: str, relative_path: str) -> dict[str, Any]:
        path = self.safe_path(config_dir, relative_path)
        if path is None or not path.exists():
            raise FileNotFoundError(relative_path)

        with path.open("r", encoding="utf-8") as handle:
            document = yaml.safe_load(handle) or {}

        if document.get("kind") != "FeatureCombinations":
            raise ValueError(f"{relative_path} is not a FeatureCombinations config")

        selected_features = document.get("features", [])
        combinations = []
        for combo_dict in document.get("combinations", []):
            feature_values: dict[str, str] = {}
            for feature, value in combo_dict.items():
                if isinstance(value, list):
                    feature_values[feature] = ", ".join(str(v) for v in value)
                else:
                    feature_values[feature] = str(value)
            combinations.append({
                "id": uuid.uuid4().hex,
                "feature_values": feature_values,
            })

        return {
            "path": relative_path,
            "kind": "FeatureCombinations",
            "available_features": [],
            "selected_features": list(selected_features),
            "combinations": combinations,
        }

    def new_state(self, relative_path: str = "") -> dict[str, Any]:
        state = super().new_state(relative_path)
        state["available_features"] = []
        state["selected_features"] = []
        return state

    def state_from_json(self, payload: str | None) -> dict[str, Any]:
        state = super().state_from_json(payload)
        state.setdefault("available_features", [])
        state.setdefault("selected_features", [])
        return state

    def to_yaml(self, state: dict[str, Any]) -> str:
        features = state.get("selected_features", [])
        combinations = []
        for item in state.get("combinations", []):
            combo: dict[str, Any] = {}
            for feature in features:
                value_text = item.get("values", {}).get(feature, "").strip()
                if not value_text:
                    continue
                if value_text == "*":
                    combo[feature] = "*"
                else:
                    values = split_csv(value_text)
                    combo[feature] = values[0] if len(values) == 1 else values
            if combo:
                combinations.append(combo)

        document: dict[str, Any] = {
            "kind": "FeatureCombinations",
            "features": features,
            "combinations": combinations or [{}],
        }
        return yaml.safe_dump(document, sort_keys=False, allow_unicode=True)

    def _blank_item(self) -> dict[str, Any]:
        return {
            "id": uuid.uuid4().hex,
            "values": {},
        }

    def update_from_form(self, state: dict[str, Any], form: Any) -> dict[str, Any]:
        updated = super().update_from_form(state, form)
        features_text = form.get("features_text", "")
        updated["selected_features"] = split_csv(features_text)
        return updated

    def _update_items_from_form(
        self, items: list[dict[str, Any]], form: Any
    ) -> list[dict[str, Any]]:
        updated: list[dict[str, Any]] = []
        for item in items:
            combo_id = item["id"]
            current = copy.deepcopy(item)
            values: dict[str, str] = {}
            for key, val in form.items():
                prefix = f"val-{combo_id}-"
                if key.startswith(prefix):
                    feature = key[len(prefix):]
                    values[feature] = val.strip()
            if values:
                current["values"] = values
            updated.append(current)
        return updated

    def _run_test(self, item: dict[str, Any], registry: Any) -> dict:
        raise NotImplementedError("FeatureCombinations does not support testing")


