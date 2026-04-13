from __future__ import annotations

import copy
import uuid
from typing import Any

import yaml

from src.editors.editor_base import BaseEditor, split_csv


class FeatureDefinitionsEditor(BaseEditor):
    kind = "FeatureDefinitions"
    dir_name = "features"
    collection_key = "features"

    def load_state(self, config_dir: str, relative_path: str) -> dict[str, Any]:
        path = self.safe_path(config_dir, relative_path)
        if path is None or not path.exists():
            raise FileNotFoundError(relative_path)

        with path.open("r", encoding="utf-8") as handle:
            document = yaml.safe_load(handle) or {}

        if document.get("kind") != "FeatureDefinitions":
            raise ValueError(f"{relative_path} is not a FeatureDefinitions config")

        features_dict = document.get("features", {})
        items = []
        for name, values in features_dict.items():
            if not isinstance(values, list):
                values = [values] if values else []
            items.append({
                "id": uuid.uuid4().hex,
                "name": str(name),
                "values_text": ", ".join(str(v) for v in values),
            })

        return {
            "path": relative_path,
            "kind": "FeatureDefinitions",
            "features": items,
        }

    def to_yaml(self, state: dict[str, Any]) -> str:
        features_dict = {}
        for item in state.get("features", []):
            name = item.get("name", "").strip()
            if not name:
                continue
            values = split_csv(item.get("values_text", ""))
            features_dict[name] = values
        document = {"kind": "FeatureDefinitions", "features": features_dict}
        return yaml.safe_dump(document, sort_keys=False, allow_unicode=True)

    def _blank_item(self) -> dict[str, Any]:
        return {
            "id": uuid.uuid4().hex,
            "name": "",
            "values_text": "",
        }

    def _update_items_from_form(
        self, items: list[dict[str, Any]], form: Any
    ) -> list[dict[str, Any]]:
        updated: list[dict[str, Any]] = []
        for item in items:
            item_id = item["id"]
            current = copy.deepcopy(item)
            current["name"] = form.get(
                f"name-{item_id}", current.get("name", "")
            ).strip()
            current["values_text"] = form.get(
                f"values_text-{item_id}", current.get("values_text", "")
            ).strip()
            updated.append(current)
        return updated

    def _run_test(self, item: dict[str, Any], registry: Any) -> dict:
        raise NotImplementedError("FeatureDefinitions does not support testing")
