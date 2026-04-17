from __future__ import annotations

import copy
import json
from typing import Any

from src.editors.configs import safe_file_path


def split_csv(value: str) -> list[str]:
    normalized = value.replace("\n", ",")
    return [item.strip() for item in normalized.split(",") if item.strip()]


class BaseEditor:
    kind: str = ""
    dir_name: str = ""
    collection_key: str = ""

    def safe_path(self, config_dir: str, relative_path: str):
        path = safe_file_path(config_dir, relative_path)
        if path is None:
            return None
        if self.dir_name not in path.parts:
            return None
        return path

    def new_state(self, relative_path: str = "") -> dict[str, Any]:
        return {
            "path": relative_path,
            "kind": self.kind,
            self.collection_key: [],
        }

    def state_to_json(self, state: dict[str, Any]) -> str:
        return json.dumps(state, ensure_ascii=False)

    def state_from_json(self, payload: str | None) -> dict[str, Any]:
        if not payload:
            return self.new_state()
        state = json.loads(payload)
        state.setdefault("kind", self.kind)
        state.setdefault("path", "")
        state.setdefault(self.collection_key, [])
        return self._ensure_ids(state)

    def update_from_form(self, state: dict[str, Any], form: Any) -> dict[str, Any]:
        updated = copy.deepcopy(state)
        updated["path"] = form.get("path", updated.get("path", "")).strip()
        updated[self.collection_key] = self._update_items_from_form(
            updated.get(self.collection_key, []), form
        )
        return updated

    def add_item(self, state: dict[str, Any]) -> dict[str, Any]:
        updated = copy.deepcopy(state)
        updated.setdefault(self.collection_key, []).append(self._blank_item())
        return updated

    def remove_item(self, state: dict[str, Any], item_id: str) -> dict[str, Any]:
        updated = copy.deepcopy(state)
        updated[self.collection_key] = [
            item
            for item in updated.get(self.collection_key, [])
            if item.get("id") != item_id
        ]
        return updated

    def save(self, config_dir: str, state: dict[str, Any]) -> str:
        relative_path = state.get("path", "").strip()
        if not relative_path:
            raise ValueError("A file path is required")

        path = self.safe_path(config_dir, relative_path)
        if path is None:
            raise ValueError(
                f"Path must point to a YAML file inside a {self.dir_name} "
                f"directory under the selected config path."
            )

        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            handle.write(self.to_yaml(state))
        return relative_path

    def _ensure_ids(self, state: dict[str, Any]) -> dict[str, Any]:
        state = copy.deepcopy(state)
        state[self.collection_key] = [
            self._ensure_item_ids(item)
            for item in state.get(self.collection_key, [])
        ]
        return state

    def _ensure_item_ids(self, item: dict[str, Any]) -> dict[str, Any]:
        current = copy.deepcopy(item)
        defaults = self._blank_item()
        for key, value in defaults.items():
            current.setdefault(key, value)
        return current

    def run_tests(
        self,
        state: dict[str, Any],
        item_id: str,
        registry: Any,
    ) -> tuple[dict[str, Any], str | None]:
        updated = copy.deepcopy(state)
        items = updated.get(self.collection_key, [])
        target = next((i for i in items if i["id"] == item_id), None)
        if target is None:
            return updated, f"{self.kind} item not found in editor state."

        try:
            target["test_results"] = self._run_test(target, registry)
        except KeyError:
            name = target.get("name", "") or target.get("ref", "")
            return updated, (
                f"'{name}' not found in saved configs — save the file first."
            )
        except Exception as exc:
            return updated, str(exc)

        return updated, None

    # --- abstract methods subclasses must implement ---

    def _blank_item(self) -> dict[str, Any]:
        raise NotImplementedError

    def load_state(self, config_dir: str, relative_path: str) -> dict[str, Any]:
        raise NotImplementedError

    def to_yaml(self, state: dict[str, Any]) -> str:
        raise NotImplementedError

    def _update_items_from_form(
        self, items: list[dict[str, Any]], form: Any
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    def _run_test(self, item: dict[str, Any], registry: Any) -> dict:
        raise NotImplementedError
