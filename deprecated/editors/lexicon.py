from __future__ import annotations

import copy
import csv as csv_mod
import io
import json
import uuid
from pathlib import Path
from typing import Any

import yaml

from src.editors.configs import safe_csv_path
from src.editors.editor_base import BaseEditor, split_csv


def _dynamic_columns(state: dict[str, Any]) -> list[str]:
    return (
        state.get("principal_parts", [])
        + state.get("lexical_features", [])
    )


class LexiconEditor(BaseEditor):
    kind = "PartOfSpeech"
    dir_name = "parts_of_speech"
    collection_key = "rows"

    # -- state lifecycle ------------------------------------------------

    def new_state(self, relative_path: str = "") -> dict[str, Any]:
        stem = Path(relative_path).stem if relative_path else ""
        return {
            "path": relative_path,
            "kind": "PartOfSpeech",
            "name": stem,
            "features": [],
            "lexical_features": [],
            "principal_parts": [],
            "rows": [],
            "columns_warning": "",
        }

    def state_from_json(self, payload: str | None) -> dict[str, Any]:
        state = super().state_from_json(payload)
        state.setdefault("name", "")
        state.setdefault("features", [])
        state.setdefault("lexical_features", [])
        state.setdefault("principal_parts", [])
        state.setdefault("columns_warning", "")
        return state

    def load_state(self, config_dir: str, relative_path: str) -> dict[str, Any]:
        path = self.safe_path(config_dir, relative_path)
        if path is None or not path.exists():
            raise FileNotFoundError(relative_path)

        with path.open("r", encoding="utf-8") as handle:
            document = yaml.safe_load(handle) or {}

        if document.get("kind") != "PartOfSpeech":
            raise ValueError(f"{relative_path} is not a PartOfSpeech config")

        name = document.get("name", path.stem)
        features = document.get("features", [])
        lexical_features = document.get("lexical_features", [])
        principal_parts = document.get("principal_parts", [])

        state: dict[str, Any] = {
            "path": relative_path,
            "kind": "PartOfSpeech",
            "name": name,
            "features": features if isinstance(features, list) else [],
            "lexical_features": (
                lexical_features if isinstance(lexical_features, list) else []
            ),
            "principal_parts": (
                principal_parts if isinstance(principal_parts, list) else []
            ),
            "rows": [],
            "columns_warning": "",
        }

        csv_path = safe_csv_path(config_dir, f"lexicon/{name}.csv")
        if csv_path is not None and csv_path.exists():
            with csv_path.open("r", encoding="utf-8") as f:
                for row_dict in csv_mod.DictReader(f):
                    row: dict[str, Any] = {"id": uuid.uuid4().hex}
                    row.update(row_dict)
                    state["rows"].append(row)

        return state

    # -- form handling --------------------------------------------------

    def update_from_form(self, state: dict[str, Any], form: Any) -> dict[str, Any]:
        updated = copy.deepcopy(state)

        updated["name"] = form.get("name", updated.get("name", "")).strip()
        name = updated["name"]
        if name:
            updated["path"] = f"parts_of_speech/{name}.yaml"

        updated["features"] = _json_list(form.get("features_json", "[]"))
        updated["lexical_features"] = _json_list(
            form.get("lexical_features_json", "[]")
        )
        updated["principal_parts"] = split_csv(
            form.get("principal_parts_text", "")
        )

        old_dyn = set(_dynamic_columns(state))
        new_dyn = set(_dynamic_columns(updated))
        dropped = old_dyn - new_dyn

        warning = ""
        if dropped:
            has_data = any(
                row.get(col, "").strip()
                for row in updated.get("rows", [])
                for col in dropped
            )
            if has_data:
                warning = (
                    f"Columns removed (data discarded): {', '.join(sorted(dropped))}"
                )
        updated["columns_warning"] = warning

        all_keys = {"id", "root", "gloss"} | new_dyn
        for row in updated.get("rows", []):
            for col in new_dyn:
                row.setdefault(col, "")
            for key in list(row.keys()):
                if key not in all_keys:
                    del row[key]

        updated["rows"] = self._update_items_from_form(
            updated.get("rows", []), form
        )
        return updated

    def _update_items_from_form(
        self, rows: list[dict[str, Any]], form: Any
    ) -> list[dict[str, Any]]:
        updated: list[dict[str, Any]] = []
        for row in rows:
            row_id = row["id"]
            current = copy.deepcopy(row)
            for key in list(current.keys()):
                if key == "id":
                    continue
                form_key = f"{key}-{row_id}"
                if form_key in form:
                    current[key] = form.get(form_key, "").strip()
            updated.append(current)
        return updated

    # -- add / remove rows ----------------------------------------------

    def add_item(self, state: dict[str, Any]) -> dict[str, Any]:
        updated = copy.deepcopy(state)
        row = self._blank_item()
        for col in _dynamic_columns(updated):
            row[col] = ""
        updated.setdefault("rows", []).append(row)
        return updated

    def _blank_item(self) -> dict[str, Any]:
        return {"id": uuid.uuid4().hex, "root": "", "gloss": ""}

    # -- serialisation --------------------------------------------------

    def to_yaml(self, state: dict[str, Any]) -> str:
        document: dict[str, Any] = {
            "kind": "PartOfSpeech",
            "name": state.get("name", ""),
        }
        if state.get("features"):
            document["features"] = state["features"]
        if state.get("lexical_features"):
            document["lexical_features"] = state["lexical_features"]
        if state.get("principal_parts"):
            document["principal_parts"] = state["principal_parts"]
        return yaml.safe_dump(document, sort_keys=False, allow_unicode=True)

    def to_csv(self, state: dict[str, Any]) -> str:
        columns = ["root", "gloss"] + _dynamic_columns(state)
        output = io.StringIO()
        writer = csv_mod.DictWriter(
            output, fieldnames=columns, extrasaction="ignore"
        )
        writer.writeheader()
        for row in state.get("rows", []):
            writer.writerow({col: row.get(col, "") for col in columns})
        return output.getvalue()

    def dynamic_columns(self, state: dict[str, Any]) -> list[str]:
        return _dynamic_columns(state)

    # -- save (two files) -----------------------------------------------

    def save(self, config_dir: str, state: dict[str, Any]) -> str:
        name = state.get("name", "").strip()
        if not name:
            raise ValueError("A part of speech name is required.")

        relative_path = f"parts_of_speech/{name}.yaml"
        yaml_path = self.safe_path(config_dir, relative_path)
        if yaml_path is None:
            raise ValueError(
                "Path must point to a YAML file inside parts_of_speech/."
            )
        yaml_path.parent.mkdir(parents=True, exist_ok=True)
        with yaml_path.open("w", encoding="utf-8") as handle:
            handle.write(self.to_yaml(state))

        csv_rel = f"lexicon/{name}.csv"
        csv_path = safe_csv_path(config_dir, csv_rel)
        if csv_path is None:
            raise ValueError("Cannot resolve lexicon CSV path.")
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with csv_path.open("w", encoding="utf-8") as handle:
            handle.write(self.to_csv(state))

        return relative_path

    def _run_test(self, item: dict[str, Any], registry: Any) -> dict:
        raise NotImplementedError("PartOfSpeech does not support testing")


def _json_list(raw: str) -> list[str]:
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    return parsed if isinstance(parsed, list) else []
