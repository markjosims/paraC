"""
Streamlit Contingent Markers Editor
===================================
A UI for creating and editing contingent feature marker YAML configs.
"""

from __future__ import annotations

import uuid
from typing import Any

import streamlit as st
import yaml
from pathlib import Path

from src.config_utils.config_walker import ConfigWalker
from src.grammar.registry.feature_marker_registry import Marker
from src.pages.editor_utils import (
    EditorBase,
    editor_guard,
    editor_header,
    editor_sidebar,
    render_marker_list,
    MARKER_WIDGET_PREFIXES,
    _MARKER_TYPE_PREFIX,
    _MARKER_VALUE_PREFIX,
    _MARKER_REPLACE_IN_PREFIX,
    _MARKER_REPLACE_OUT_PREFIX,
    _MARKER_ORDER_PREFIX,
)

_config_kind = "ContingentFeatureMarkers"
_config_key = "contingent_feature_marker_configs"

# Prefix constants
_GLOBAL_ORDER_PREFIX = "global-order-"
_OUTER_FEATURE_PREFIX = "outer-feature-"
_INNER_FEATURE_PREFIX = "inner-feature-"
_OUTER_VAL_PREFIX = "outer-val-"
_INNER_VAL_PREFIX = "inner-val-"
_REMOVE_OUTER_PREFIX = "remove-outer-"
_REMOVE_INNER_PREFIX = "remove-inner-"

_WIDGET_PREFIXES: list[str] = [
    _GLOBAL_ORDER_PREFIX,
    _OUTER_FEATURE_PREFIX,
    _INNER_FEATURE_PREFIX,
    _OUTER_VAL_PREFIX,
    _INNER_VAL_PREFIX,
    _REMOVE_OUTER_PREFIX,
    _REMOVE_INNER_PREFIX,
] + MARKER_WIDGET_PREFIXES

_help_str = """
Contingent marker files define how realizations depend on two features.
- **Outer feature**: Partitions the markers into groups.
- **Inner feature**: Defines the specific values marked within each group.
"""


class ContingentMarkersEditor(EditorBase):
    """
    Editor for ContingentFeatureMarkers YAML configs.

    self.data keys:
        outer_feature  — str
        inner_feature  — str
        global_order   — str
        global_markers — list[Marker]
        outer_entries  — list[dict] (uuid, outer_value, inner_entries: list[dict])
            inner_entry: (uuid, inner_value, markers: list[Marker])
    """

    def __init__(self) -> None:
        super().__init__(kind=_config_kind, config_key=_config_key)

    def build_state_from_config(self, config_object: dict) -> dict:
        outer_feature = config_object.get("outer_feature", "")
        inner_feature = config_object.get("inner_feature", "")
        global_order = config_object.get("global_order", "")

        def load_markers(raw: Any) -> list[Marker]:
            if not raw:
                return []
            if isinstance(raw, dict):
                raw = [raw]
            return [Marker.from_config(m) for m in raw]

        global_markers = load_markers(config_object.get("global_markers", []))

        markers_raw = config_object.get("markers", [])
        outer_entries = []
        for o_config in markers_raw:
            o_val = o_config.get("outer_feature_value", "")
            inner_entries = []
            for i_val, m_list_raw in (o_config.get("inner_feature_values", {})).items():
                inner_entries.append(
                    {
                        "uuid": str(uuid.uuid4()),
                        "inner_feature_value": i_val,
                        "markers": load_markers(m_list_raw),
                    }
                )
            outer_entries.append(
                {
                    "uuid": str(uuid.uuid4()),
                    "outer_feature_value": o_val,
                    "inner_entries": inner_entries,
                }
            )

        return {
            "outer_feature": outer_feature,
            "inner_feature": inner_feature,
            "global_order": global_order,
            "global_markers": global_markers,
            "outer_entries": outer_entries,
        }

    def read_form_to_state(self) -> None:
        """Sync widget values back to self.data."""
        # 1. Top-level fields
        o_feat = st.session_state.get(self.get_widget_key(_OUTER_FEATURE_PREFIX, "main"))
        if o_feat is not None:
            self.data["outer_feature"] = o_feat
        
        i_feat = st.session_state.get(self.get_widget_key(_INNER_FEATURE_PREFIX, "main"))
        if i_feat is not None:
            self.data["inner_feature"] = i_feat

        g_order = st.session_state.get(self.get_widget_key(_GLOBAL_ORDER_PREFIX, "main"))
        if g_order is not None:
            self.data["global_order"] = g_order

        # 2. Global markers
        self._sync_marker_list(self.data["global_markers"], "global")

        # 3. Outer/Inner entries
        for outer in self.data["outer_entries"]:
            o_uid = outer["uuid"]
            o_val = self.get_node_widget(_OUTER_VAL_PREFIX, o_uid)
            if o_val is not None:
                outer["outer_feature_value"] = o_val
            
            for inner in outer["inner_entries"]:
                i_uid = inner["uuid"]
                i_val = self.get_node_widget(_INNER_VAL_PREFIX, i_uid)
                if i_val is not None:
                    inner["inner_feature_value"] = i_val
                
                self._sync_marker_list(inner["markers"], f"inner-{i_uid}")

    def _sync_marker_list(self, markers: list[Marker], scope: str) -> None:
        """Helper to sync a list of Marker objects from widgets."""
        for marker in markers:
            m_uid = marker.uuid
            m_type = self.get_node_widget(_MARKER_TYPE_PREFIX, scope, suffix=m_uid)
            m_order = self.get_node_widget(_MARKER_ORDER_PREFIX, scope, suffix=m_uid)

            if m_type is not None:
                marker.type = m_type
            if m_order is not None:
                marker.order = m_order if m_order.strip() else None

            if marker.type == "replace":
                r_in = self.get_node_widget(_MARKER_REPLACE_IN_PREFIX, scope, suffix=m_uid)
                r_out = self.get_node_widget(_MARKER_REPLACE_OUT_PREFIX, scope, suffix=m_uid)
                if r_in is not None and r_out is not None:
                    marker.value = (r_in, r_out)
            else:
                val = self.get_node_widget(_MARKER_VALUE_PREFIX, scope, suffix=m_uid)
                if val is not None:
                    marker.value = val

    def to_yaml(self) -> dict:
        def serialize_markers(markers: list[Marker]) -> list[dict] | None:
            if not markers:
                return None
            result = []
            for m in markers:
                d = {"type": m.type, "value": m.value}
                if m.order:
                    d["order"] = m.order
                result.append(d)
            return result

        doc = {
            "kind": self.kind,
            "outer_feature": self.data["outer_feature"],
            "inner_feature": self.data["inner_feature"],
        }
        if self.data["global_order"]:
            doc["global_order"] = self.data["global_order"]

        global_markers = serialize_markers(self.data["global_markers"])
        if global_markers:
            doc["global_markers"] = global_markers

        markers_list = []
        for outer in self.data["outer_entries"]:
            o_val = outer["outer_feature_value"]
            if not o_val:
                continue
            
            i_dict = {}
            for inner in outer["inner_entries"]:
                i_val = inner["inner_feature_value"]
                if i_val:
                    i_dict[i_val] = serialize_markers(inner["markers"])
            
            markers_list.append({
                "outer_feature_value": o_val,
                "inner_feature_values": i_dict
            })
        
        doc["markers"] = markers_list
        return doc

    def insert_outer(self) -> None:
        self.data["outer_entries"].append({
            "uuid": str(uuid.uuid4()),
            "outer_feature_value": "",
            "inner_entries": []
        })

    def remove_outer(self, o_uid: str) -> None:
        self.data["outer_entries"] = [o for o in self.data["outer_entries"] if o["uuid"] != o_uid]

    def insert_inner(self, outer: dict) -> None:
        outer["inner_entries"].append({
            "uuid": str(uuid.uuid4()),
            "inner_feature_value": "",
            "markers": []
        })

    def remove_inner(self, outer: dict, i_uid: str) -> None:
        outer["inner_entries"] = [i for i in outer["inner_entries"] if i["uuid"] != i_uid]

    def add_marker(self, markers: list[Marker]) -> None:
        markers.append(Marker(value="marker value...", type="suffix"))

    def remove_marker(self, markers: list[Marker], m_uuid: str) -> None:
        markers[:] = [m for m in markers if m.uuid != m_uuid]


def contingent_markers_toolbar(editor: ContingentMarkersEditor) -> None:
    col_add, col_save, col_preview_toggle, _ = st.columns([1.4, 1.2, 1.6, 5])

    with col_add:
        if st.button("➕ Add outer value", use_container_width=True):
            editor.insert_outer()
            st.rerun()

    with col_save:
        if st.button("💾 Save YAML", use_container_width=True, type="primary"):
            stem = st.session_state.get("file_name", "").strip()
            if not stem:
                st.error("Enter a file name before saving.")
            else:
                try:
                    editor.save(stem)
                    st.toast(f"✅ Saved as `{stem}`", icon="✅")
                except (ValueError, OSError) as exc:
                    st.error(str(exc))

    with col_preview_toggle:
        show_preview = st.toggle("Show YAML preview", value=False)

    if show_preview:
        with st.container(border=True):
            st.caption("YAML preview — reflects unsaved edits")
            st.code(yaml.dump(editor.to_yaml(), allow_unicode=True, sort_keys=False))


def contingent_markers_page() -> None:
    st.set_page_config(
        page_title="Contingent Markers Editor",
        page_icon="👯",
        layout="wide",
    )

    config_dir: str = st.session_state["config_dir"]
    config_walker: ConfigWalker = st.session_state["config_walker"]
    cm_files = config_walker.config_filemap[_config_key]

    editor_sidebar(
        kind=_config_kind,
        editor_class=ContingentMarkersEditor,
        config_dir=config_dir,
        config_walker=config_walker,
        kind_files=cm_files,
        help_str=_help_str,
    )

    editor = editor_guard(kind=_config_kind)
    editor.read_form_to_state()
    editor_header(kind=_config_kind, editor=editor)

    grammar = st.session_state.get("grammar")
    available_features = []
    available_rules = []
    available_principal_parts = []
    if grammar:
        available_features = list(grammar.feature_orchestrator.feature_values_registry.features_to_values.keys())
        available_rules = list(grammar.fst_orchestrator.rule_registry.data.keys())
        pp_sets = set()
        for pos_config in grammar.lexicon_registry.config_objects.values():
            for col in pos_config.get("columns", []):
                pp_sets.add(col)
        available_principal_parts = sorted(list(pp_sets))

    # 1. Config section
    with st.expander("Configuration", expanded=not bool(editor.data["outer_entries"])):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.selectbox(
                "Outer Feature",
                options=[""] + available_features,
                index=available_features.index(editor.data["outer_feature"]) + 1 if editor.data["outer_feature"] in available_features else 0,
                key=editor.get_widget_key(_OUTER_FEATURE_PREFIX, "main")
            )
        with col2:
            st.selectbox(
                "Inner Feature",
                options=[""] + available_features,
                index=available_features.index(editor.data["inner_feature"]) + 1 if editor.data["inner_feature"] in available_features else 0,
                key=editor.get_widget_key(_INNER_FEATURE_PREFIX, "main")
            )
        with col3:
            st.text_input(
                "Global Order Stage",
                value=editor.data["global_order"],
                key=editor.get_widget_key(_GLOBAL_ORDER_PREFIX, "main"),
                placeholder="argument_marker"
            )
        
        render_marker_list(
            editor.data["global_markers"],
            "global",
            editor,
            available_rules,
            available_principal_parts,
            label="Global Markers"
        )

    toolbar_placeholder = st.empty()
    st.divider()

    # 2. Entries section
    o_feat = editor.data["outer_feature"]
    i_feat = editor.data["inner_feature"]
    o_vals = grammar.feature_orchestrator.feature_values_registry.features_to_values.get(o_feat, []) if grammar else []
    i_vals = grammar.feature_orchestrator.feature_values_registry.features_to_values.get(i_feat, []) if grammar else []

    for outer in editor.data["outer_entries"]:
        o_uid = outer["uuid"]
        with st.container(border=True):
            o_col, o_btn_add, o_btn_del = st.columns([4, 1, 1])
            with o_col:
                if o_vals:
                    st.selectbox(
                        f"Outer Value ({o_feat})",
                        options=[""] + o_vals,
                        index=o_vals.index(outer["outer_feature_value"]) + 1 if outer["outer_feature_value"] in o_vals else 0,
                        key=editor.get_widget_key(_OUTER_VAL_PREFIX, o_uid)
                    )
                else:
                    st.text_input("Outer Value", value=outer["outer_feature_value"], key=editor.get_widget_key(_OUTER_VAL_PREFIX, o_uid))
            
            with o_btn_add:
                st.write("##")
                if st.button("➕ Inner", key=f"add-i-{o_uid}", use_container_width=True):
                    editor.insert_inner(outer)
                    st.rerun()
            with o_btn_del:
                st.write("##")
                if st.button("✕ Outer", key=editor.get_widget_key(_REMOVE_OUTER_PREFIX, o_uid), use_container_width=True):
                    editor.remove_outer(o_uid)
                    st.rerun()
            
            for inner in outer["inner_entries"]:
                i_uid = inner["uuid"]
                with st.container(border=True):
                    i_col, i_btn_del = st.columns([5, 1])
                    with i_col:
                        if i_vals:
                            st.selectbox(
                                f"Inner Value ({i_feat})",
                                options=[""] + i_vals,
                                index=i_vals.index(inner["inner_feature_value"]) + 1 if inner["inner_feature_value"] in i_vals else 0,
                                key=editor.get_widget_key(_INNER_VAL_PREFIX, i_uid)
                            )
                        else:
                            st.text_input("Inner Value", value=inner["inner_feature_value"], key=editor.get_widget_key(_INNER_VAL_PREFIX, i_uid))
                    
                    with i_btn_del:
                        st.write("##")
                        if st.button("✕ Inner", key=editor.get_widget_key(_REMOVE_INNER_PREFIX, i_uid), use_container_width=True):
                            editor.remove_inner(outer, i_uid)
                            st.rerun()
                    
                    render_marker_list(
                        inner["markers"],
                        f"inner-{i_uid}",
                        editor,
                        available_rules,
                        available_principal_parts
                    )

    with toolbar_placeholder.container():
        contingent_markers_toolbar(editor)


if __name__ == "__main__":
    contingent_markers_page()
