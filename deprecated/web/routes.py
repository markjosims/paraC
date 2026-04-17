from __future__ import annotations

from pathlib import Path
import unicodedata
from typing import Any
from loguru import logger

from flask import Blueprint, jsonify, redirect, render_template, request, url_for
import threading
import yaml
import os

from src.editors.configs import (
    delete_config_file,
    group_yaml_files_by_kind,
    known_config_kinds,
    list_config_yaml_files,
    load_config_entry,
    new_text_config_state,
    rename_config_file,
    save_config_text,
    suggested_config_path,
)
from src.editors.contingent_markers import ContingentFeatureMarkersEditor
from src.registry.grammar_registry import GrammarRegistry
from src.editors.feature_combinations import FeatureCombinationsEditor
from src.editors.feature_markers import FeatureMarkersEditor
from src.editors.features import FeatureDefinitionsEditor
from src.editors.inventory import InventoryEditor
from src.editors.lexicon import LexiconEditor
from src.editors.paradigms import ParadigmEditor
from src.editors.patterns import PatternsEditor
from src.editors.rules import RulesEditor
from flask import current_app as app


bp = Blueprint("web", __name__)
GRAMMAR_REGISTRY_CACHE: dict[str, tuple[float, GrammarRegistry]] = {}
GRAPH_BUILD_STATUS: dict[tuple[str, str], dict] = {}
# key: (config_dir, paradigm_name)
# value: {"status": "idle" | "building" | "done" | "error", "error": str | None}

EDITORS = {
    "Inventory": InventoryEditor(),
    "Patterns": PatternsEditor(),
    "Rules": RulesEditor(),
    "FeatureDefinitions": FeatureDefinitionsEditor(),
    "FeatureCombinations": FeatureCombinationsEditor(),
    "FeatureMarkers": FeatureMarkersEditor(),
    "ContingentFeatureMarkers": ContingentFeatureMarkersEditor(),
    "Paradigm": ParadigmEditor(),
    "PartOfSpeech": LexiconEditor(),
}


@bp.get("/")
def home():
    return render_template(
        "index.html",
        active_tab="home",
        state={},
        selected_path="",
        selected_kind=None,
        editor_kind="",
        state_json="",
        yaml_preview="",
        sidebar_phone_trees=[],
        sidebar_flag_trees=[],
        sidebar_patterns=[],
    )


@bp.get("/config")
def config():
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
        return redirect(url_for("web.config", error=page_context["error"]))

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
            page_context = _config_page_context()
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


@bp.post("/config/rename")
def config_rename():
    old_path = request.form.get("old_path", "").strip()
    new_path = request.form.get("new_path", "").strip()
    try:
        config_dir = _local_config_dir()
        rename_config_file(config_dir, old_path, new_path)
        return redirect(
            url_for("web.config", path=new_path, message=f"Renamed to {new_path}")
        )
    except (RuntimeError, ValueError, FileNotFoundError) as exc:
        return redirect(url_for("web.config", path=old_path, error=str(exc)))


@bp.post("/config/delete")
def config_delete():
    path = request.form.get("path", "").strip()
    try:
        config_dir = _local_config_dir()
        delete_config_file(config_dir, path)
        return redirect(url_for("web.config", message=f"Deleted {path}"))
    except (RuntimeError, ValueError, FileNotFoundError) as exc:
        return redirect(url_for("web.config", path=path, error=str(exc)))


@bp.post("/inventory/add-child/<node_id>")
def inventory_add_child(node_id: str):
    form = _normalize_form_data(request.form)
    page_context = _config_page_context()
    if page_context.get("error"):
        return redirect(url_for("web.config", error=page_context["error"]))

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
        return redirect(url_for("web.config", error=page_context["error"]))

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


@bp.post("/features/add-entry")
def features_add_entry():
    return _add_item_handler("FeatureDefinitions")


@bp.post("/features/remove-entry/<feature_id>")
def features_remove_entry(feature_id: str):
    return _remove_item_handler("FeatureDefinitions", feature_id)


@bp.post("/feature-combinations/add-entry")
def feature_combinations_add_entry():
    return _add_item_handler("FeatureCombinations")


@bp.post("/feature-combinations/remove-entry/<combo_id>")
def feature_combinations_remove_entry(combo_id: str):
    return _remove_item_handler("FeatureCombinations", combo_id)


@bp.post("/feature-markers/add-entry")
def feature_markers_add_entry():
    return _add_item_handler("FeatureMarkers")


@bp.post("/feature-markers/remove-entry/<entry_id>")
def feature_markers_remove_entry(entry_id: str):
    return _remove_item_handler("FeatureMarkers", entry_id)


@bp.post("/feature-markers/add-global-marker")
def feature_markers_add_global_marker():
    return _marker_editor_state_handler(
        "FeatureMarkers", lambda editor, state: editor.add_global_marker(state)
    )


@bp.post("/feature-markers/add-marker/<entry_id>")
def feature_markers_add_entry_marker(entry_id: str):
    return _marker_editor_state_handler(
        "FeatureMarkers",
        lambda editor, state: editor.add_entry_marker(state, entry_id),
    )


@bp.post("/feature-markers/remove-marker/<marker_id>")
def feature_markers_remove_marker(marker_id: str):
    return _marker_editor_state_handler(
        "FeatureMarkers",
        lambda editor, state: editor.remove_marker(state, marker_id),
    )


@bp.post("/contingent-markers/add-entry")
def contingent_markers_add_entry():
    return _add_item_handler("ContingentFeatureMarkers")


@bp.post("/contingent-markers/remove-entry/<outer_id>")
def contingent_markers_remove_entry(outer_id: str):
    return _remove_item_handler("ContingentFeatureMarkers", outer_id)


@bp.post("/contingent-markers/add-global-marker")
def contingent_markers_add_global_marker():
    return _marker_editor_state_handler(
        "ContingentFeatureMarkers",
        lambda editor, state: editor.add_global_marker(state),
    )


@bp.post("/contingent-markers/add-inner/<outer_id>")
def contingent_markers_add_inner_entry(outer_id: str):
    return _marker_editor_state_handler(
        "ContingentFeatureMarkers",
        lambda editor, state: editor.add_inner_entry(state, outer_id),
    )


@bp.post("/contingent-markers/remove-inner/<inner_id>")
def contingent_markers_remove_inner_entry(inner_id: str):
    return _marker_editor_state_handler(
        "ContingentFeatureMarkers",
        lambda editor, state: editor.remove_inner_entry(state, inner_id),
    )


@bp.post("/contingent-markers/add-marker/<inner_id>")
def contingent_markers_add_inner_marker(inner_id: str):
    return _marker_editor_state_handler(
        "ContingentFeatureMarkers",
        lambda editor, state: editor.add_inner_marker(state, inner_id),
    )


@bp.post("/contingent-markers/remove-marker/<marker_id>")
def contingent_markers_remove_marker(marker_id: str):
    return _marker_editor_state_handler(
        "ContingentFeatureMarkers",
        lambda editor, state: editor.remove_marker(state, marker_id),
    )


@bp.post("/paradigms/add-entry")
def paradigms_add_entry():
    return _add_item_handler("Paradigm")


@bp.post("/paradigms/remove-entry/<item_id>")
def paradigms_remove_entry(item_id: str):
    return _remove_item_handler("Paradigm", item_id)


@bp.post("/paradigms/add-order-stage")
def paradigms_add_order_stage():
    return _marker_editor_state_handler(
        "Paradigm", lambda editor, state: editor.add_order_stage(state)
    )


@bp.post("/paradigms/remove-order-stage/<stage_id>")
def paradigms_remove_order_stage(stage_id: str):
    return _marker_editor_state_handler(
        "Paradigm", lambda editor, state: editor.remove_order_stage(state, stage_id)
    )


@bp.post("/paradigms/add-global-marker")
def paradigms_add_global_marker():
    return _marker_editor_state_handler(
        "Paradigm", lambda editor, state: editor.add_global_marker(state)
    )


@bp.post("/paradigms/remove-marker/<marker_id>")
def paradigms_remove_marker(marker_id: str):
    return _marker_editor_state_handler(
        "Paradigm", lambda editor, state: editor.remove_marker(state, marker_id)
    )


@bp.post("/paradigms/add-contingent-marker")
def paradigms_add_contingent_marker():
    return _marker_editor_state_handler(
        "Paradigm", lambda editor, state: editor.add_contingent_marker(state)
    )


@bp.post("/paradigms/remove-contingent-marker/<marker_id>")
def paradigms_remove_contingent_marker(marker_id: str):
    return _marker_editor_state_handler(
        "Paradigm",
        lambda editor, state: editor.remove_contingent_marker(state, marker_id),
    )


@bp.post("/paradigms/add-lexical-feature")
def paradigms_add_lexical_feature():
    return _marker_editor_state_handler(
        "Paradigm", lambda editor, state: editor.add_lexical_feature(state)
    )


@bp.post("/paradigms/remove-lexical-feature/<feature_id>")
def paradigms_remove_lexical_feature(feature_id: str):
    return _marker_editor_state_handler(
        "Paradigm",
        lambda editor, state: editor.remove_lexical_feature(state, feature_id),
    )


@bp.get("/parse")
def parse():
    tool = request.args.get("tool", "word").strip()
    selected = request.args.get("paradigm_name", "").strip()
    return _render_parse_page(parse_tool=tool, parse_selected_paradigm=selected)


@bp.post("/parse/build-graphs")
def parse_build_graphs():
    paradigm_name = request.form.get("paradigm_name", "").strip()
    try:
        config_dir = _local_config_dir()
        registry = _get_grammar_registry(config_dir)
    except Exception as exc:
        return redirect(url_for("web.parse", tool="word", paradigm_name=paradigm_name))

    cache_key = (str(Path(config_dir)), paradigm_name)
    if GRAPH_BUILD_STATUS.get(cache_key, {}).get("status") == "building":
        return redirect(url_for("web.parse", tool="word", paradigm_name=paradigm_name))

    paradigm = registry.paradigms.get(paradigm_name) if registry.paradigms else None
    if paradigm is None:
        return redirect(url_for("web.parse", tool="word", paradigm_name=paradigm_name))

    GRAPH_BUILD_STATUS[cache_key] = {"status": "building", "error": None}

    def _build():
        try:
            paradigm.build_all_graphs()
            GRAPH_BUILD_STATUS[cache_key] = {"status": "done", "error": None}
        except Exception as exc:
            GRAPH_BUILD_STATUS[cache_key] = {"status": "error", "error": str(exc)}

    threading.Thread(target=_build, daemon=True).start()
    return redirect(url_for("web.parse", tool="word", paradigm_name=paradigm_name))


@bp.get("/parse/build-status")
def parse_build_status():
    try:
        config_dir = _local_config_dir()
        registry = _get_grammar_registry(config_dir)
    except Exception as exc:
        return jsonify({"paradigms": {}, "error": str(exc)})

    result = {}
    paradigms = registry.paradigms or {}
    for name, paradigm in paradigms.items():
        cache_key = (str(Path(config_dir)), name)
        build_info = GRAPH_BUILD_STATUS.get(
            cache_key, {"status": "idle", "error": None}
        )
        result[name] = {
            "main_graphs_built": bool(paradigm.main_graphs_built),
            "edit_graphs_built": bool(paradigm.edit_graphs_built),
            "status": build_info["status"],
            "error": build_info["error"],
        }
    return jsonify({"paradigms": result})


@bp.post("/parse/word")
def parse_word():
    paradigm_name = request.form.get("paradigm_name", "").strip()
    query = request.form.get("query", "").strip()
    inexact = request.form.get("inexact", "") == "1"

    if not paradigm_name:
        return _render_parse_page(
            parse_tool="word",
            error="Please select a paradigm.",
            parse_selected_paradigm=paradigm_name,
            parse_query=query,
            parse_inexact=inexact,
        )

    if not query:
        return _render_parse_page(
            parse_tool="word",
            error="Please enter a form to parse.",
            parse_selected_paradigm=paradigm_name,
            parse_query=query,
            parse_inexact=inexact,
        )

    try:
        config_dir = _local_config_dir()
        registry = _get_grammar_registry(config_dir)
    except Exception as exc:
        return _render_parse_page(
            parse_tool="word",
            error=f"Could not load grammar registry: {exc}",
            parse_selected_paradigm=paradigm_name,
            parse_query=query,
            parse_inexact=inexact,
        )

    paradigm = registry.paradigms.get(paradigm_name)
    if paradigm is None:
        return _render_parse_page(
            parse_tool="word",
            error=f"Paradigm '{paradigm_name}' not found in registry.",
            parse_selected_paradigm=paradigm_name,
            parse_query=query,
            parse_inexact=inexact,
        )

    try:
        if inexact:
            raw_results = paradigm.search_parses(query)
            parse_results = []
            for item in raw_results:
                parse_str = item.get("parse", "")
                idx = parse_str.find("[")
                if idx >= 0:
                    root = parse_str[:idx]
                    feature_str = parse_str[idx:]
                else:
                    root = parse_str
                    feature_str = ""
                parse_results.append(
                    {
                        "form": item.get("form", query),
                        "root": root,
                        "parse": feature_str,
                        "num_edits": item.get("weight", 0),
                    }
                )
        else:
            raw_results = paradigm.get_parses(query)
            parse_results = []
            for parse_str in raw_results:
                idx = parse_str.find("[")
                if idx >= 0:
                    root = parse_str[:idx]
                    feature_str = parse_str[idx:]
                else:
                    root = parse_str
                    feature_str = ""
                parse_results.append(
                    {
                        "root": root,
                        "parse": feature_str,
                    }
                )
    except (ValueError, Exception) as exc:
        return _render_parse_page(
            parse_tool="word",
            error=str(exc),
            parse_selected_paradigm=paradigm_name,
            parse_query=query,
            parse_inexact=inexact,
        )

    return _render_parse_page(
        parse_tool="word",
        parse_results=parse_results,
        parse_selected_paradigm=paradigm_name,
        parse_query=query,
        parse_inexact=inexact,
    )


@bp.get("/inflect")
def inflect():
    tool = request.args.get("tool", "stages").strip()
    return _render_inflect_page(inflect_tool=tool)


@bp.post("/inflect/run")
def inflect_run():
    paradigm_name = request.form.get("paradigm_name", "").strip()
    stem = request.form.get("stem", "").strip()

    # Collect feature values from fv-* form fields
    feature_values: dict[str, str] = {}
    for key, value in request.form.items():
        if key.startswith("fv-") and value:
            feature_values[key[3:]] = value

    if not paradigm_name:
        return _render_inflect_page(
            inflect_tool="stages",
            error="Please select a paradigm.",
            inflect_selected_paradigm=paradigm_name,
            inflect_selected_stem=stem,
            inflect_selected_features=feature_values,
        )

    if not stem:
        return _render_inflect_page(
            inflect_tool="stages",
            error="Please enter a stem.",
            inflect_selected_paradigm=paradigm_name,
            inflect_selected_stem=stem,
            inflect_selected_features=feature_values,
        )

    try:
        config_dir = _local_config_dir()
        registry = _get_grammar_registry(config_dir)
    except Exception as exc:
        return _render_inflect_page(
            inflect_tool="stages",
            error=f"Could not load grammar registry: {exc}",
            inflect_selected_paradigm=paradigm_name,
            inflect_selected_stem=stem,
            inflect_selected_features=feature_values,
        )

    paradigm = registry.paradigms.get(paradigm_name)
    if paradigm is None:
        return _render_inflect_page(
            inflect_tool="stages",
            error=f"Paradigm '{paradigm_name}' not found in registry.",
            inflect_selected_paradigm=paradigm_name,
            inflect_selected_stem=stem,
            inflect_selected_features=feature_values,
        )

    try:
        results = paradigm.get_inflection_stages(stem, feature_values)
    except (ValueError, Exception) as exc:
        logger.exception(exc)
        return _render_inflect_page(
            inflect_tool="stages",
            error=str(exc),
            inflect_selected_paradigm=paradigm_name,
            inflect_selected_stem=stem,
            inflect_selected_features=feature_values,
        )

    return _render_inflect_page(
        inflect_tool="stages",
        inflect_results=results,
        inflect_selected_paradigm=paradigm_name,
        inflect_selected_stem=stem,
        inflect_selected_features=feature_values,
    )


@bp.post("/inflect/view")
def view_paradigm_run():
    paradigm_name = request.form.get("paradigm_name", "").strip()
    stem = request.form.get("stem", "").strip()
    max_rows_str = request.form.get("max_rows", "100").strip()

    try:
        max_rows = max(1, int(max_rows_str))
    except ValueError:
        max_rows = 100

    # Collect pinned feature values from fv-* form fields
    fixed_features: dict[str, str] = {}
    for key, value in request.form.items():
        if key.startswith("fv-") and value:
            fixed_features[key[3:]] = value

    view_state = dict(
        view_selected_paradigm=paradigm_name,
        view_selected_stem=stem,
        view_selected_features=fixed_features,
        view_selected_max_rows=max_rows,
    )

    if not paradigm_name:
        return _render_inflect_page(
            inflect_tool="view",
            error="Please select a paradigm.",
            **view_state,
        )

    if not stem:
        return _render_inflect_page(
            inflect_tool="view",
            error="Please enter a stem.",
            **view_state,
        )

    try:
        config_dir = _local_config_dir()
        registry = _get_grammar_registry(config_dir)
    except Exception as exc:
        return _render_inflect_page(
            inflect_tool="view",
            error=f"Could not load grammar registry: {exc}",
            **view_state,
        )

    paradigm = registry.paradigms.get(paradigm_name)
    if paradigm is None:
        return _render_inflect_page(
            inflect_tool="view",
            error=f"Paradigm '{paradigm_name}' not found in registry.",
            **view_state,
        )

    try:
        results = paradigm.get_subparadigm_table(
            stem,
            fixed_features=fixed_features or None,
            only_free_feature_columns=True,
            max_rows=max_rows,
        )
    except (ValueError, Exception) as exc:
        return _render_inflect_page(
            inflect_tool="view",
            error=str(exc),
            **view_state,
        )

    if results:
        columns = sorted(k for k in results[0] if k != "form") + ["form"]
    else:
        columns = ["form"]

    return _render_inflect_page(
        inflect_tool="view",
        view_results=results,
        view_result_columns=columns,
        view_max_rows=max_rows,
        **view_state,
    )


@bp.post("/lexicon/add-row")
def lexicon_add_row():
    return _add_item_handler("PartOfSpeech")


@bp.post("/lexicon/remove-row/<row_id>")
def lexicon_remove_row(row_id: str):
    return _remove_item_handler("PartOfSpeech", row_id)


@bp.post("/rules/add-entry")
def rules_add_entry():
    return _add_item_handler("Rules")


@bp.post("/rules/remove-entry/<rule_id>")
def rules_remove_entry(rule_id: str):
    return _remove_item_handler("Rules", rule_id)


def _add_item_handler(kind: str):
    page_context = _config_page_context()
    if page_context.get("error"):
        return redirect(url_for("web.config", error=page_context["error"]))

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
        return redirect(url_for("web.config", error=page_context["error"]))

    editor = EDITORS[kind]
    state = editor.state_from_json(request.form.get("state"))
    state = editor.update_from_form(state, request.form)

    config_dir = _local_config_dir()
    registry = _get_grammar_registry(config_dir)
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
        return redirect(url_for("web.config", error=page_context["error"]))

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


def _marker_editor_state_handler(kind: str, mutator):
    page_context = _config_page_context()
    if page_context.get("error"):
        return redirect(url_for("web.config", error=page_context["error"]))

    editor = EDITORS[kind]
    state = editor.state_from_json(request.form.get("state"))
    state = editor.update_from_form(state, request.form)
    state = mutator(editor, state)
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
        "selected_source_label": os.path.basename(config_dir),
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


def _serialize_inventory_tree(item) -> dict:
    return {
        "value": item.value,
        "type": item.type,
        "children": [_serialize_inventory_tree(child) for child in item.children],
    }


def _has_phone(item) -> bool:
    return item.type == "phone" or any(_has_phone(c) for c in item.children)


def _has_flag(item) -> bool:
    return item.type == "flag" or any(_has_flag(c) for c in item.children)


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

    extra: dict[str, Any] = {}
    kind = state.get("kind")

    registry = None
    features_to_values = {}

    if kind in (
        "PartOfSpeech",
        "FeatureMarkers",
        "ContingentFeatureMarkers",
        "FeatureCombinations",
        "Paradigm",
        "Rules",
    ):
        try:
            registry = _get_grammar_registry(_local_config_dir())
            features_to_values = (
                registry.feature_values_registry.feature_values_registry.features_to_values
            )
        except Exception:
            registry = None
            features_to_values = {}

    if kind in ("FeatureMarkers", "ContingentFeatureMarkers", "Paradigm", "Rules"):
        try:
            if registry is not None and registry.fst_registry is not None:
                extra["available_rules"] = sorted(registry.fst_registry.rules.keys())
            else:
                extra["available_rules"] = []
        except Exception:
            extra["available_rules"] = []

    if kind == "PartOfSpeech":
        editor = EDITORS["PartOfSpeech"]
        extra["available_features"] = sorted(features_to_values.keys())
        extra["features_to_values"] = features_to_values
        extra["dynamic_columns"] = editor.dynamic_columns(state)
        extra["csv_preview"] = editor.to_csv(state)

    if kind in ("FeatureMarkers", "ContingentFeatureMarkers"):
        extra["features_to_values"] = features_to_values

    if kind == "FeatureCombinations":
        state["available_features"] = sorted(features_to_values.keys())

    if kind == "Paradigm":
        if registry is not None and registry.is_initialized:
            state["available_part_of_speech"] = sorted(
                registry.lexicon_registry.data.keys()
            )
            state["available_feature_markers"] = sorted(
                registry.marker_registry.feature_markers.keys()
            )
            state["available_contingent_markers"] = sorted(
                registry.marker_registry.contingent_markers.keys()
            )
            state["available_feature_combinations"] = sorted(
                registry.feature_values_registry.feature_combinations.keys()
            )
            state["available_features_to_values"] = features_to_values
            state["available_patterns"] = (
                sorted(registry.fst_registry.patterns.keys())
                if registry.fst_registry
                else []
            )
        else:
            state["available_part_of_speech"] = []
            state["available_feature_markers"] = []
            state["available_contingent_markers"] = []
            state["available_feature_combinations"] = []
            state["available_features_to_values"] = {}
            state["available_patterns"] = []

    # Right reference sidebar data
    try:
        if registry is None:
            registry = _get_grammar_registry(_local_config_dir())
        fst_reg = registry.fst_registry
        inv_reg = fst_reg.inventory_registry
        all_items = inv_reg.data.values()
        root_items = [item for item in all_items if item.parent is None]
        extra["sidebar_phone_trees"] = [
            _serialize_inventory_tree(i) for i in root_items if _has_phone(i)
        ]
        extra["sidebar_flag_trees"] = [
            _serialize_inventory_tree(i) for i in root_items if _has_flag(i)
        ]
        extra["sidebar_patterns"] = [
            {
                "ref": p._ref,
                "value": p.value if isinstance(p.value, str) else " | ".join(p.value),
            }
            for p in fst_reg.patterns.values()
        ]
    except Exception:
        extra["sidebar_phone_trees"] = []
        extra["sidebar_flag_trees"] = []
        extra["sidebar_patterns"] = []

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
        **extra,
    )


def _render_parse_page(
    parse_tool: str = "word",
    message: str | None = None,
    error: str | None = None,
    parse_results: list[dict] | None = None,
    parse_selected_paradigm: str = "",
    parse_query: str = "",
    parse_inexact: bool = False,
):
    parse_registry_error = None
    paradigm_names: list[str] = []

    try:
        config_dir = _local_config_dir()
        yaml_files = list_config_yaml_files(config_dir)
        paradigm_names = [
            item["label"] for item in yaml_files if item.get("kind") == "Paradigm"
        ]
    except Exception as exc:
        parse_registry_error = (
            "Could not load grammar registry. Ensure your config files "
            "define at least one valid Paradigm before using the Parse tab. "
            f"({exc})"
        )

    return render_template(
        "index.html",
        active_tab="parse",
        parse_tool=parse_tool,
        paradigm_names=paradigm_names,
        parse_registry_error=parse_registry_error,
        parse_results=parse_results,
        parse_selected_paradigm=parse_selected_paradigm,
        parse_query=parse_query,
        parse_inexact=parse_inexact,
        message=message,
        error=error,
        # Defaults for config-tab vars that base template may reference
        state={},
        selected_path="",
        selected_kind=None,
        editor_kind="",
        state_json="",
        yaml_preview="",
        sidebar_phone_trees=[],
        sidebar_flag_trees=[],
        sidebar_patterns=[],
    )


def _render_inflect_page(
    inflect_tool: str = "stages",
    message: str | None = None,
    error: str | None = None,
    # Inflect stages state
    inflect_results: list[dict[str, str]] | None = None,
    inflect_selected_paradigm: str = "",
    inflect_selected_stem: str = "",
    inflect_selected_features: dict[str, str] | None = None,
    # View paradigm state
    view_results: list[dict[str, str]] | None = None,
    view_result_columns: list[str] | None = None,
    view_max_rows: int = 100,
    view_selected_paradigm: str = "",
    view_selected_stem: str = "",
    view_selected_features: dict[str, str] | None = None,
    view_selected_max_rows: int = 100,
):
    inflect_registry_error = None
    paradigm_names: list[str] = []
    paradigm_features: dict[str, dict[str, list[str]]] = {}
    paradigm_fixed_features: dict[str, dict[str, str]] = {}
    paradigm_roots: dict[str, list[str]] = {}

    try:
        config_dir = _local_config_dir()
        yaml_files = list_config_yaml_files(config_dir)
        paradigm_names = [
            item["label"] for item in yaml_files if item.get("kind") == "Paradigm"
        ]
        registry = _get_grammar_registry(config_dir)
        for name, paradigm in registry.paradigms.items():
            fixed = paradigm.fixed_features or {}
            if paradigm.feature_value_combinations is not None:
                ftv = dict(paradigm.feature_value_combinations.features_to_values)
            else:
                ftv = {f.name: list(f.values) for f in paradigm.features}
            paradigm_features[name] = {k: v for k, v in ftv.items() if k not in fixed}
            paradigm_fixed_features[name] = fixed
            try:
                paradigm_roots[name] = paradigm.lexicon.get_roots()
            except Exception:
                paradigm_roots[name] = []
    except Exception as exc:
        inflect_registry_error = (
            "Could not load grammar registry. Ensure your config files "
            "define at least one valid Paradigm before using the Inflect tab. "
            f"({exc})"
        )
        logger.exception(inflect_registry_error)

    return render_template(
        "index.html",
        active_tab="inflect",
        inflect_tool=inflect_tool,
        paradigm_names=paradigm_names,
        paradigm_features=paradigm_features,
        paradigm_fixed_features=paradigm_fixed_features,
        paradigm_roots=paradigm_roots,
        inflect_registry_error=inflect_registry_error,
        inflect_results=inflect_results,
        inflect_selected_paradigm=inflect_selected_paradigm,
        inflect_selected_stem=inflect_selected_stem,
        inflect_selected_features=inflect_selected_features or {},
        # View paradigm state
        view_results=view_results,
        view_result_columns=view_result_columns or ["form"],
        view_max_rows=view_max_rows,
        view_selected_paradigm=view_selected_paradigm,
        view_selected_stem=view_selected_stem,
        view_selected_features=view_selected_features or {},
        view_selected_max_rows=view_selected_max_rows,
        message=message,
        error=error,
        # Defaults for config-tab vars that base template may reference
        state={},
        selected_path="",
        selected_kind=None,
        editor_kind="",
        state_json="",
        yaml_preview="",
        sidebar_phone_trees=[],
        sidebar_flag_trees=[],
        sidebar_patterns=[],
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


def _get_grammar_registry(config_dir: str) -> GrammarRegistry:
    cache_key = str(Path(config_dir))
    current_stamp = _yaml_tree_mtime(cache_key)
    cached = GRAMMAR_REGISTRY_CACHE.get(cache_key)
    if (cached is not None) and (cached[0] == current_stamp):
        if not cached[1].is_initialized:
            logger.info(
                f"Found uninitialized GrammarRegistry, attempting to rebuilt from config dir '{config_dir}'"
            )
        else:
            logger.info(f"Using cached GrammarRegistry for config dir '{config_dir}'")
            return cached[1]

    logger.info(f"Loading GrammarRegistry for config dir '{config_dir}'")
    registry = GrammarRegistry.from_config_dir(cache_key)
    GRAMMAR_REGISTRY_CACHE[cache_key] = (current_stamp, registry)
    logger.info(f"Loaded GrammarRegistry with stamp {current_stamp}")
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
