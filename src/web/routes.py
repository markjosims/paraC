from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from flask import Blueprint, redirect, render_template, request, url_for
import yaml
import pynini

from src.web.configs import (
    create_manifest_session,
    get_upload_session,
    group_yaml_files_by_kind,
    known_config_kinds,
    list_config_yaml_files,
    list_uploaded_yaml_files,
    load_config_entry,
    load_uploaded_config_entry,
    materialize_upload_session,
    new_text_config_state,
    normalize_config_dir,
    save_config_text,
    save_uploaded_config_text,
    suggested_config_path,
)
from src.registry.fst_registry import FstRegistry
from src.web.inventory import (
    add_child_node,
    add_root_node,
    inventory_yaml,
    load_inventory_state,
    load_uploaded_inventory_state,
    remove_node,
    save_inventory,
    save_uploaded_inventory,
    state_from_json,
    state_to_json,
    update_state_from_form,
)
from src.web.patterns import (
    add_pattern,
    load_patterns_state,
    load_uploaded_patterns_state,
    patterns_yaml,
    remove_pattern,
    save_patterns,
    save_uploaded_patterns,
    state_from_json as patterns_state_from_json,
    state_to_json as patterns_state_to_json,
    update_state_from_form as update_patterns_state_from_form,
)
from flask import current_app as app


bp = Blueprint("web", __name__)
FST_REGISTRY_CACHE: dict[str, tuple[float, FstRegistry]] = {}


@bp.post("/scan-config")
def scan_config():
    manifest = request.form.get("manifest", "")
    if not manifest:
        return render_template("select_config.html", error="Choose a directory first.")
    token = create_manifest_session(manifest)
    return redirect(url_for("web.index", config_token=token))


@bp.get("/")
def index():
    config_token = request.args.get("config_token", "").strip()
    selected_config_dir = request.args.get("config_dir", "").strip()
    selected_path = request.args.get("path", "").strip()
    message = request.args.get("message")
    error = request.args.get("error")

    # check for default config dir in dev environment
    if app.debug and not config_token and not selected_config_dir:
        selected_config_dir = os.environ.get("CONFIG_DIR", "").strip()

    if not config_token and not selected_config_dir:
        return render_template("select_config.html", error=error)

    source = _resolve_source(config_token, selected_config_dir)
    if source.get("error"):
        return render_template("select_config.html", error=source["error"])

    state = _load_editor_state(source, selected_path)
    return _render_page(
        source,
        state,
        selected_path=selected_path,
        selected_kind=state.get("kind") or None,
        message=message,
        error=error,
    )


@bp.route("/parser-test", methods=["GET", "POST"])
def parser_test():
    config_token = request.values.get("config_token", "").strip()
    selected_config_dir = request.values.get("config_dir", "").strip()

    

    selected_source_label = ""

    if config_token:
        upload_session = get_upload_session(config_token)
        if upload_session is None:
            return render_template("select_config.html", error="Uploaded config session not found.")
        try:
            config_dir = str(materialize_upload_session(config_token))
        except ValueError as exc:
            return render_template("select_config.html", error=str(exc))
        selected_source_label = upload_session["label"]
    else:
        if not selected_config_dir:
            return render_template("select_config.html", error="Select a valid config directory first.")
        normalized_config_dir = normalize_config_dir(selected_config_dir)
        if normalized_config_dir is None:
            return render_template("select_config.html", error=f"Directory not found: {selected_config_dir}")
        config_dir = str(normalized_config_dir)
        selected_source_label = config_dir

    parser_input = request.values.get("parser_input", "").strip()
    selected_pattern = request.values.get("path", "").strip()
    outputs: list[str] = []
    message = None
    error = None

    try:
        registry = _get_fst_registry(config_dir)
    except Exception as exc:
        registry = None
        error = str(exc)

    pattern_items: list[dict[str, str]] = []
    if registry is not None:
        pattern_items = [
            {
                "label": ref,
                "path": ref,
                "source": Path(pattern.source).name if getattr(pattern, "source", None) else "",
            }
            for ref, pattern in sorted(registry.patterns.items())
        ]
        if not selected_pattern and pattern_items:
            selected_pattern = pattern_items[0]["path"]

    selected_pattern_obj = registry.patterns.get(selected_pattern) if registry is not None and selected_pattern else None

    if request.method == "POST" and registry is not None and selected_pattern:
        try:
            pattern_fsa = registry.parse_pattern(selected_pattern)
            input_fsa = registry.fsa(parser_input)
            intersection = pynini.intersect(pattern_fsa, input_fsa)
            if intersection.start() == pynini.NO_STATE_ID:
                message = f"{selected_pattern} does not accept {parser_input!r}."
            else:
                outputs = registry.fsm_strings(intersection, nshortest=20)
                message = f"{selected_pattern} accepts {parser_input!r}."
        except Exception as exc:
            error = str(exc)

    return render_template(
        "parser_test.html",
        active_tab="parser",
        selected_config_dir="" if config_token else config_dir,
        config_token=config_token,
        selected_source_label=selected_source_label,
        accordion_groups=[
            {
                "kind": "Pattern",
                "dom_id": "parser-group-pattern",
                "count": len(pattern_items),
                "config_items": pattern_items,
            }
        ],
        selected_path=selected_pattern,
        selected_pattern=selected_pattern,
        selected_pattern_obj=selected_pattern_obj,
        parser_input=parser_input,
        outputs=outputs,
        message=message,
        error=error,
    )


@bp.post("/config")
def config_editor():
    action = request.form.get("action", "")
    config_token = request.form.get("config_token", "").strip()
    selected_config_dir = request.form.get("config_dir", "").strip()
    if not config_token and not selected_config_dir:
        return render_template("select_config.html", error="Select a valid config directory first.")
    source = _resolve_source(config_token, selected_config_dir)
    if source.get("error"):
        return render_template("select_config.html", error=source["error"])

    editor_kind = request.form.get("editor_kind", "").strip()
    message = None
    error = None

    if action == "new":
        new_kind = request.form.get("new_kind", "").strip() or "Inventory"
        file_stem = request.form.get("file_stem", "").strip()
        state = _new_editor_state(new_kind, suggested_config_path(new_kind, file_stem))
        if new_kind == "Inventory":
            state = add_root_node(state)
    else:
        state = _state_from_form(request.form, editor_kind)
        if action == "add-root" and state.get("kind") == "Inventory":
            state = add_root_node(state)

    if action == "save":
        try:
            _save_state(source, state)
            prefix = "Updated uploaded copy of" if source["config_token"] else "Saved"
            message = f"{prefix} {state['path']}"
        except ValueError as exc:
            error = str(exc)

    selected_path = state.get("path", "")
    return _render_page(
        source,
        state,
        selected_path=selected_path,
        selected_kind=state.get("kind") or None,
        message=message,
        error=error,
    )


@bp.post("/inventory/add-child/<node_id>")
def inventory_add_child(node_id: str):
    source = _resolve_source(
        request.form.get("config_token", "").strip(),
        request.form.get("config_dir", "").strip(),
    )
    if source.get("error"):
        return render_template("select_config.html", error=source["error"])

    state = state_from_json(request.form.get("state"))
    state = update_state_from_form(state, request.form)
    state = add_child_node(state, node_id)
    return _render_page(
        source,
        state,
        selected_path=state.get("path", ""),
        selected_kind="Inventory",
    )


@bp.post("/inventory/remove-node/<node_id>")
def inventory_remove_node(node_id: str):
    source = _resolve_source(
        request.form.get("config_token", "").strip(),
        request.form.get("config_dir", "").strip(),
    )
    if source.get("error"):
        return render_template("select_config.html", error=source["error"])

    state = state_from_json(request.form.get("state"))
    state = update_state_from_form(state, request.form)
    state = remove_node(state, node_id)
    return _render_page(
        source,
        state,
        selected_path=state.get("path", ""),
        selected_kind="Inventory",
    )


@bp.post("/patterns/add-entry")
def patterns_add_entry():
    source = _resolve_source(
        request.form.get("config_token", "").strip(),
        request.form.get("config_dir", "").strip(),
    )
    if source.get("error"):
        return render_template("select_config.html", error=source["error"])

    state = patterns_state_from_json(request.form.get("state"))
    state = update_patterns_state_from_form(state, request.form)
    state = add_pattern(state)
    return _render_page(
        source,
        state,
        selected_path=state.get("path", ""),
        selected_kind="Patterns",
    )


@bp.post("/patterns/remove-entry/<pattern_id>")
def patterns_remove_entry(pattern_id: str):
    source = _resolve_source(
        request.form.get("config_token", "").strip(),
        request.form.get("config_dir", "").strip(),
    )
    if source.get("error"):
        return render_template("select_config.html", error=source["error"])

    state = patterns_state_from_json(request.form.get("state"))
    state = update_patterns_state_from_form(state, request.form)
    state = remove_pattern(state, pattern_id)
    return _render_page(
        source,
        state,
        selected_path=state.get("path", ""),
        selected_kind="Patterns",
    )


def _resolve_source(config_token: str, selected_config_dir: str) -> dict[str, Any]:
    if config_token:
        upload_session = get_upload_session(config_token)
        if upload_session is None:
            return {"error": "Uploaded config session not found."}
        yaml_files = list_uploaded_yaml_files(config_token)
        return {
            "selected_source_label": upload_session["label"],
            "selected_config_dir": "",
            "config_token": config_token,
            "yaml_files": yaml_files,
        }

    if not selected_config_dir:
        return {"error": None}

    normalized_config_dir = normalize_config_dir(selected_config_dir)
    if normalized_config_dir is None:
        return {"error": f"Directory not found: {selected_config_dir}"}

    config_dir = str(normalized_config_dir)
    return {
        "selected_source_label": config_dir,
        "selected_config_dir": config_dir,
        "config_token": "",
        "yaml_files": list_config_yaml_files(config_dir),
    }


def _load_editor_state(source: dict[str, Any], selected_path: str) -> dict[str, Any]:
    if not selected_path:
        return new_text_config_state()

    try:
        entry = _load_entry(source, selected_path)
    except (FileNotFoundError, ValueError):
        return new_text_config_state(relative_path=selected_path)

    if entry.get("kind") == "Inventory":
        return _load_inventory_state_for_source(source, selected_path)
    if entry.get("kind") == "Patterns":
        return _load_patterns_state_for_source(source, selected_path)

    return {
        "path": selected_path,
        "kind": entry.get("kind", ""),
        "content": entry.get("content", ""),
    }


def _load_entry(source: dict[str, Any], relative_path: str) -> dict[str, Any]:
    if source["config_token"]:
        return load_uploaded_config_entry(source["config_token"], relative_path)
    return load_config_entry(source["selected_config_dir"], relative_path)


def _load_inventory_state_for_source(source: dict[str, Any], relative_path: str) -> dict[str, Any]:
    if source["config_token"]:
        return load_uploaded_inventory_state(source["config_token"], relative_path)
    return load_inventory_state(source["selected_config_dir"], relative_path)


def _load_patterns_state_for_source(source: dict[str, Any], relative_path: str) -> dict[str, Any]:
    if source["config_token"]:
        return load_uploaded_patterns_state(source["config_token"], relative_path)
    return load_patterns_state(source["selected_config_dir"], relative_path)


def _new_editor_state(kind: str, relative_path: str) -> dict[str, Any]:
    if kind == "Inventory":
        return {
            "path": relative_path,
            "kind": "Inventory",
            "nodes": [],
        }
    if kind == "Patterns":
        return {
            "path": relative_path,
            "kind": "Patterns",
            "patterns": [],
        }
    return new_text_config_state(kind, relative_path)


def _state_from_form(form: Any, editor_kind: str) -> dict[str, Any]:
    if editor_kind == "Inventory":
        state = state_from_json(form.get("state"))
        return update_state_from_form(state, form)
    if editor_kind == "Patterns":
        state = patterns_state_from_json(form.get("state"))
        return update_patterns_state_from_form(state, form)

    content = form.get("content", "")
    return {
        "path": form.get("path", "").strip(),
        "kind": _kind_from_content(content) or editor_kind,
        "content": content,
    }


def _save_state(source: dict[str, Any], state: dict[str, Any]) -> str:
    if state.get("kind") == "Inventory":
        if source["config_token"]:
            return save_uploaded_inventory(source["config_token"], state)
        return save_inventory(source["selected_config_dir"], state)
    if state.get("kind") == "Patterns":
        if source["config_token"]:
            return save_uploaded_patterns(source["config_token"], state)
        return save_patterns(source["selected_config_dir"], state)

    if source["config_token"]:
        return save_uploaded_config_text(source["config_token"], state["path"], state["content"])
    return save_config_text(source["selected_config_dir"], state["path"], state["content"])


def _render_page(
    source: dict[str, Any],
    state: dict[str, Any],
    selected_path: str = "",
    selected_kind: str | None = None,
    message: str | None = None,
    error: str | None = None,
):
    yaml_files = source.get("yaml_files", [])
    return render_template(
        "index.html",
        active_tab="config",
        selected_source_label=source.get("selected_source_label", ""),
        selected_config_dir=source.get("selected_config_dir", ""),
        config_token=source.get("config_token", ""),
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
    if state.get("kind") == "Inventory":
        return state_to_json(state)
    if state.get("kind") == "Patterns":
        return patterns_state_to_json(state)
    return ""


def _editor_yaml_preview(state: dict[str, Any]) -> str:
    if state.get("kind") == "Inventory":
        return inventory_yaml(state)
    if state.get("kind") == "Patterns":
        return patterns_yaml(state)
    return state.get("content", "")


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
