from __future__ import annotations

from pathlib import Path
import unicodedata
from typing import Any

from flask import Blueprint, redirect, render_template, request, url_for
import yaml

from src.web.configs import (
    group_yaml_files_by_kind,
    known_config_kinds,
    list_config_yaml_files,
    load_config_entry,
    new_text_config_state,
    save_config_text,
    suggested_config_path,
)
from src.registry.fst_registry import FstRegistry
from src.web.inventory import InventoryEditor
from src.web.patterns import PatternsEditor
from src.web.rules import RulesEditor
from flask import current_app as app


bp = Blueprint("web", __name__)
FST_REGISTRY_CACHE: dict[str, tuple[float, FstRegistry]] = {}

EDITORS = {
    "Inventory": InventoryEditor(),
    "Patterns": PatternsEditor(),
    "Rules": RulesEditor(),
}


@bp.get("/")
def index():
    selected_path = request.args.get("path", "").strip()
    message = request.args.get("message")
    error = request.args.get("error")

    page_context = _config_page_context()
    if page_context.get("error"):
        state = new_text_config_state(relative_path=selected_path)
        return _render_page(
            state,
            page_context=page_context,
            selected_path=selected_path,
            selected_kind=state.get("kind") or None,
            error=page_context["error"],
        )

    state = _load_editor_state(selected_path)
    return _render_page(
        state,
        page_context=page_context,
        selected_path=selected_path,
        selected_kind=state.get("kind") or None,
        message=message,
        error=error,
    )


@bp.post("/config")
def config_editor():
    form = _normalize_form_data(request.form)
    action = form.get("action", "")
    page_context = _config_page_context()
    if page_context.get("error"):
        return redirect(url_for("web.index", error=page_context["error"]))

    editor_kind = form.get("editor_kind", "").strip()
    message = None
    error = None

    if action == "new":
        new_kind = form.get("new_kind", "").strip() or "Inventory"
        file_stem = form.get("file_stem", "").strip()
        state = _new_editor_state(new_kind, suggested_config_path(new_kind, file_stem))
        editor = EDITORS.get(new_kind)
        if new_kind == "Inventory" and editor is not None:
            state = editor.add_item(state)
    else:
        state = _state_from_form(form, editor_kind)
        if action == "add-root" and state.get("kind") == "Inventory":
            editor = EDITORS["Inventory"]
            state = editor.add_item(state)

    if action == "save":
        try:
            _save_state(state)
            message = f"Saved {state['path']}"
        except ValueError as exc:
            error = str(exc)

    selected_path = state.get("path", "")
    return _render_page(
        state,
        page_context=page_context,
        selected_path=selected_path,
        selected_kind=state.get("kind") or None,
        message=message,
        error=error,
    )


@bp.post("/inventory/add-child/<node_id>")
def inventory_add_child(node_id: str):
    form = _normalize_form_data(request.form)
    page_context = _config_page_context()
    if page_context.get("error"):
        return redirect(url_for("web.index", error=page_context["error"]))

    editor = EDITORS["Inventory"]
    state = editor.state_from_json(form.get("state"))
    state = editor.update_from_form(state, form)
    state = editor.add_child_node(state, node_id)
    return _render_page(
        state,
        page_context=page_context,
        selected_path=state.get("path", ""),
        selected_kind="Inventory",
    )


@bp.post("/inventory/remove-node/<node_id>")
def inventory_remove_node(node_id: str):
    page_context = _config_page_context()
    if page_context.get("error"):
        return redirect(url_for("web.index", error=page_context["error"]))

    editor = EDITORS["Inventory"]
    state = editor.state_from_json(request.form.get("state"))
    state = editor.update_from_form(state, request.form)
    state = editor.remove_item(state, node_id)
    return _render_page(
        state,
        page_context=page_context,
        selected_path=state.get("path", ""),
        selected_kind="Inventory",
    )


@bp.post("/patterns/add-entry")
def patterns_add_entry():
    return _add_item_handler("Patterns")


@bp.post("/patterns/remove-entry/<pattern_id>")
def patterns_remove_entry(pattern_id: str):
    return _remove_item_handler("Patterns", pattern_id)


@bp.post("/patterns/run-tests/<pattern_id>")
def patterns_run_tests(pattern_id: str):
    return _run_tests_handler("Patterns", pattern_id)


@bp.post("/rules/run-tests/<rule_id>")
def rules_run_tests(rule_id: str):
    return _run_tests_handler("Rules", rule_id)


@bp.post("/rules/add-entry")
def rules_add_entry():
    return _add_item_handler("Rules")


@bp.post("/rules/remove-entry/<rule_id>")
def rules_remove_entry(rule_id: str):
    return _remove_item_handler("Rules", rule_id)


def _add_item_handler(kind: str):
    page_context = _config_page_context()
    if page_context.get("error"):
        return redirect(url_for("web.index", error=page_context["error"]))

    editor = EDITORS[kind]
    state = editor.state_from_json(request.form.get("state"))
    state = editor.update_from_form(state, request.form)
    state = editor.add_item(state)
    return _render_page(
        state,
        page_context=page_context,
        selected_path=state.get("path", ""),
        selected_kind=kind,
    )


def _run_tests_handler(kind: str, item_id: str):
    page_context = _config_page_context()
    if page_context.get("error"):
        return redirect(url_for("web.index", error=page_context["error"]))

    editor = EDITORS[kind]
    state = editor.state_from_json(request.form.get("state"))
    state = editor.update_from_form(state, request.form)

    config_dir = _local_config_dir()
    registry = _get_fst_registry(config_dir)
    state, error = editor.run_tests(state, item_id, registry)

    return _render_page(
        state,
        page_context=page_context,
        selected_path=state.get("path", ""),
        selected_kind=kind,
        error=error,
    )


def _remove_item_handler(kind: str, item_id: str):
    page_context = _config_page_context()
    if page_context.get("error"):
        return redirect(url_for("web.index", error=page_context["error"]))

    editor = EDITORS[kind]
    state = editor.state_from_json(request.form.get("state"))
    state = editor.update_from_form(state, request.form)
    state = editor.remove_item(state, item_id)
    return _render_page(
        state,
        page_context=page_context,
        selected_path=state.get("path", ""),
        selected_kind=kind,
    )


def _config_page_context() -> dict[str, Any]:
    try:
        config_dir = _local_config_dir()
    except RuntimeError as exc:
        return {
            "error": str(exc),
            "selected_source_label": "",
            "yaml_files": [],
        }

    return {
        "selected_source_label": config_dir,
        "yaml_files": list_config_yaml_files(config_dir),
    }


def _load_editor_state(selected_path: str) -> dict[str, Any]:
    if not selected_path:
        return new_text_config_state()

    try:
        entry = load_config_entry(_local_config_dir(), selected_path)
    except (FileNotFoundError, ValueError):
        return new_text_config_state(relative_path=selected_path)

    editor = EDITORS.get(entry.get("kind"))
    if editor is not None:
        return editor.load_state(_local_config_dir(), selected_path)

    return {
        "path": selected_path,
        "kind": entry.get("kind", ""),
        "content": entry.get("content", ""),
    }


def _new_editor_state(kind: str, relative_path: str) -> dict[str, Any]:
    editor = EDITORS.get(kind)
    if editor is not None:
        return editor.new_state(relative_path)
    return new_text_config_state(kind, relative_path)


def _state_from_form(form: Any, editor_kind: str) -> dict[str, Any]:
    editor = EDITORS.get(editor_kind)
    if editor is not None:
        state = editor.state_from_json(form.get("state"))
        return editor.update_from_form(state, form)

    content = form.get("content", "")
    return {
        "path": form.get("path", "").strip(),
        "kind": _kind_from_content(content) or editor_kind,
        "content": content,
    }


def _save_state(state: dict[str, Any]) -> str:
    editor = EDITORS.get(state.get("kind"))
    if editor is not None:
        return editor.save(_local_config_dir(), state)

    return save_config_text(_local_config_dir(), state["path"], state["content"])


def _render_page(
    state: dict[str, Any],
    page_context: dict[str, Any] | None = None,
    selected_path: str = "",
    selected_kind: str | None = None,
    message: str | None = None,
    error: str | None = None,
):
    if page_context is None:
        page_context = _config_page_context()
    yaml_files = page_context["yaml_files"]
    return render_template(
        "index.html",
        active_tab="config",
        selected_source_label=page_context["selected_source_label"],
        yaml_files=yaml_files,
        yaml_groups=group_yaml_files_by_kind(yaml_files),
        available_kinds=known_config_kinds(yaml_files),
        state=state,
        selected_path=selected_path,
        selected_kind=selected_kind,
        editor_kind=state.get("kind", ""),
        state_json=_editor_state_json(state),
        yaml_preview=_editor_yaml_preview(state),
        message=message,
        error=error,
    )


def _kind_from_content(content: str) -> str:
    try:
        document = yaml.safe_load(content) or {}
    except yaml.YAMLError:
        return ""
    kind = document.get("kind") if isinstance(document, dict) else ""
    return kind if isinstance(kind, str) else ""


def _editor_state_json(state: dict[str, Any]) -> str:
    editor = EDITORS.get(state.get("kind"))
    return editor.state_to_json(state) if editor is not None else ""


def _editor_yaml_preview(state: dict[str, Any]) -> str:
    editor = EDITORS.get(state.get("kind"))
    return editor.to_yaml(state) if editor is not None else state.get("content", "")


def _local_config_dir() -> str:
    config_dir = app.config.get("CONFIG_DIR")
    if not config_dir:
        raise RuntimeError("CONFIG_DIR is not configured for the Flask app.")
    return str(config_dir)


def _get_fst_registry(config_dir: str) -> FstRegistry:
    cache_key = str(Path(config_dir))
    current_stamp = _yaml_tree_mtime(cache_key)
    cached = FST_REGISTRY_CACHE.get(cache_key)
    if cached is not None and cached[0] == current_stamp:
        return cached[1]

    registry = FstRegistry.from_config_dir(cache_key)
    FST_REGISTRY_CACHE[cache_key] = (current_stamp, registry)
    return registry


def _yaml_tree_mtime(config_dir: str) -> float:
    root = Path(config_dir)
    mtimes = [path.stat().st_mtime for path in root.rglob("*.y*ml")]
    return max(mtimes, default=0.0)


def _normalize_form_data(
    form, skip=frozenset(["state", "name", "editor_kind", "path"])
):
    normalized_form = {}
    for key, value in form.items():
        if key in skip:
            normalized_form[key] = value
            continue
        normalized_form[key] = unicodedata.normalize("NFKD", value)
    return normalized_form
