from __future__ import annotations

import copy
import uuid
from typing import Any


MARKER_TYPES = (
    "prefix",
    "suffix",
    "replace",
    "suppletion",
    "rule",
)


def blank_marker_row() -> dict[str, str]:
    return {
        "id": uuid.uuid4().hex,
        "type": "suffix",
        "value": "",
        "replace_input": "",
        "replace_output": "",
        "order": "",
    }


def blank_stem_selector() -> dict[str, Any]:
    return {
        "id": uuid.uuid4().hex,
        "enabled": False,
        "value": "",
    }


def blank_marker_list() -> dict[str, Any]:
    return {
        "stem_selector": blank_stem_selector(),
        "markers": [],
    }


def blank_feature_entry() -> dict[str, Any]:
    return {
        "id": uuid.uuid4().hex,
        "feature_value": "",
        "marker_list": blank_marker_list(),
    }


def blank_inner_entry() -> dict[str, Any]:
    return {
        "id": uuid.uuid4().hex,
        "inner_feature_value": "",
        "marker_list": blank_marker_list(),
    }


def blank_outer_entry() -> dict[str, Any]:
    return {
        "id": uuid.uuid4().hex,
        "outer_feature_value": "",
        "inner_entries": [blank_inner_entry()],
    }


def ensure_marker_row_ids(marker: dict[str, Any]) -> dict[str, Any]:
    current = copy.deepcopy(marker or {})
    defaults = blank_marker_row()
    for key, value in defaults.items():
        current.setdefault(key, value)
    return current


def ensure_marker_list_ids(marker_list: dict[str, Any] | None) -> dict[str, Any]:
    current = copy.deepcopy(marker_list or {})
    current.setdefault("stem_selector", blank_stem_selector())
    stem = copy.deepcopy(current["stem_selector"] or {})
    stem_defaults = blank_stem_selector()
    for key, value in stem_defaults.items():
        stem.setdefault(key, value)
    stem["enabled"] = bool(stem.get("enabled"))
    stem["value"] = str(stem.get("value", ""))
    current["stem_selector"] = stem
    current["markers"] = [
        ensure_marker_row_ids(marker)
        for marker in current.get("markers", [])
    ]
    return current


def normalize_marker_list(config_value: Any) -> dict[str, Any]:
    normalized = blank_marker_list()

    if config_value is None:
        return normalized

    items = config_value if isinstance(config_value, list) else [config_value]
    for item in items:
        if not isinstance(item, dict):
            continue

        marker_type = str(item.get("type", "")).strip()
        value = item.get("value", "")
        order = str(item.get("order", "") or "")

        if marker_type == "principal_part":
            normalized["stem_selector"]["enabled"] = True
            normalized["stem_selector"]["value"] = str(value)
            continue

        row = blank_marker_row()
        row["type"] = marker_type or "suffix"
        row["order"] = order
        if marker_type == "replace":
            if isinstance(value, (list, tuple)) and len(value) >= 2:
                row["replace_input"] = str(value[0])
                row["replace_output"] = str(value[1])
        else:
            row["value"] = str(value)
        normalized["markers"].append(row)

    return normalized


def serialize_marker_list(marker_list_state: dict[str, Any]) -> Any:
    marker_list = ensure_marker_list_ids(marker_list_state)
    items: list[dict[str, Any]] = []

    stem = marker_list["stem_selector"]
    stem_value = str(stem.get("value", "")).strip()
    if stem.get("enabled") and stem_value:
        items.append({
            "type": "principal_part",
            "value": stem_value,
        })

    for row in marker_list.get("markers", []):
        row_type = str(row.get("type", "")).strip()
        if not row_type:
            continue

        entry: dict[str, Any] = {"type": row_type}
        order = str(row.get("order", "")).strip()
        if row_type == "replace":
            replace_input = str(row.get("replace_input", "")).strip()
            replace_output = str(row.get("replace_output", "")).strip()
            if not replace_input and not replace_output:
                continue
            entry["value"] = [replace_input, replace_output]
        else:
            value = str(row.get("value", "")).strip()
            if not value:
                continue
            entry["value"] = value

        if order:
            entry["order"] = order
        items.append(entry)

    if not items:
        return None
    if len(items) == 1:
        return items[0]
    return items


def update_marker_list_from_form(
    marker_list: dict[str, Any],
    form: Any,
    prefix: str,
) -> dict[str, Any]:
    updated = ensure_marker_list_ids(marker_list)
    stem = copy.deepcopy(updated["stem_selector"])
    stem["enabled"] = bool(form.get(f"{prefix}-stem-enabled"))
    stem["value"] = form.get(
        f"{prefix}-stem-value",
        stem.get("value", ""),
    ).strip()
    updated["stem_selector"] = stem

    rows: list[dict[str, Any]] = []
    for row in updated.get("markers", []):
        row_id = row["id"]
        current = ensure_marker_row_ids(row)
        current["type"] = form.get(
            f"type-{row_id}",
            current.get("type", "suffix"),
        ).strip() or "suffix"
        current["value"] = form.get(
            f"value-{row_id}",
            current.get("value", ""),
        ).strip()
        current["replace_input"] = form.get(
            f"replace-input-{row_id}",
            current.get("replace_input", ""),
        ).strip()
        current["replace_output"] = form.get(
            f"replace-output-{row_id}",
            current.get("replace_output", ""),
        ).strip()
        current["order"] = form.get(
            f"order-{row_id}",
            current.get("order", ""),
        ).strip()
        rows.append(current)
    updated["markers"] = rows
    return updated


def add_marker_row(marker_list: dict[str, Any]) -> dict[str, Any]:
    updated = ensure_marker_list_ids(marker_list)
    updated["markers"].append(blank_marker_row())
    return updated


def remove_marker_row(marker_list: dict[str, Any], marker_id: str) -> dict[str, Any]:
    updated = ensure_marker_list_ids(marker_list)
    updated["markers"] = [
        row for row in updated.get("markers", [])
        if row.get("id") != marker_id
    ]
    return updated
