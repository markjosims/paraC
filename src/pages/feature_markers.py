"""
Streamlit Feature Markers Editor
================================
A UI for creating and editing feature marker YAML configs.
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

_config_kind = "FeatureMarkers"
_config_key = "feature_marker_configs"

# Prefix constants
_GLOBAL_ORDER_PREFIX = "global-order-"
_FEATURE_PREFIX = "feature-select-"
_INHERITS_PREFIX = "inherits-select-"
_ENTRY_VAL_PREFIX = "entry-val-"
_REMOVE_ENTRY_PREFIX = "remove-entry-"

_WIDGET_PREFIXES: list[str] = [
    _GLOBAL_ORDER_PREFIX,
    _FEATURE_PREFIX,
    _INHERITS_PREFIX,
    _ENTRY_VAL_PREFIX,
    _REMOVE_ENTRY_PREFIX,
] + MARKER_WIDGET_PREFIXES

_help_str = """
Feature marker files define how specific feature values are realized morphologically.
Markers can be prefixes, suffixes, replacements, or suppletive forms.
You can also reference phonological rules or principal parts.
"""


class FeatureMarkersEditor(EditorBase):
    """
    Editor for FeatureMarkers YAML configs.

    self.data keys:
        feature        — str
        global_order   — str
        inherits       — str
        global_markers — list[Marker]
        entries        — list[dict] (uuid, feature_value, markers: list[Marker])
    """

    def __init__(self) -> None:
        super().__init__(kind=_config_kind, config_key=_config_key)

    def build_state_from_config(self, config_object: dict) -> dict:
        feature = config_object.get("feature", "")
        global_order = config_object.get("global_order", "")
        inherits = config_object.get("inherits", "")

        def load_markers(raw: Any) -> list[Marker]:
            if not raw:
                return []
            if isinstance(raw, dict):
                raw = [raw]
            return [Marker.from_config(m) for m in raw]

        global_markers = load_markers(config_object.get("global_markers", []))

        markers_raw = config_object.get("markers", {})
        entries = []
        for val, m_list_raw in markers_raw.items():
            entries.append(
                {
                    "uuid": str(uuid.uuid4()),
                    "feature_value": val,
                    "markers": load_markers(m_list_raw),
                }
            )

        return {
            "feature": feature,
            "global_order": global_order,
            "inherits": inherits,
            "global_markers": global_markers,
            "entries": entries,
        }

    def read_form_to_state(self) -> None:
        """Sync widget values back to self.data."""
        # 1. Top-level fields
        feature_val = st.session_state.get(self.get_widget_key(_FEATURE_PREFIX, "main"))
        if feature_val is not None:
            self.data["feature"] = feature_val

        inherits_val = st.session_state.get(self.get_widget_key(_INHERITS_PREFIX, "main"))
        if inherits_val is not None:
            self.data["inherits"] = inherits_val

        global_order_val = st.session_state.get(
            self.get_widget_key(_GLOBAL_ORDER_PREFIX, "main")
        )
        if global_order_val is not None:
            self.data["global_order"] = global_order_val

        # 2. Global markers
        self._sync_marker_list(self.data["global_markers"], "global")

        # 3. Entries
        for entry in self.data["entries"]:
            e_uid = entry["uuid"]
            val = self.get_node_widget(_ENTRY_VAL_PREFIX, e_uid)
            if val is not None:
                entry["feature_value"] = val
            self._sync_marker_list(entry["markers"], f"entry-{e_uid}")

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
            "feature": self.data["feature"],
        }
        if self.data["inherits"]:
            doc["inherits"] = self.data["inherits"]
        if self.data["global_order"]:
            doc["global_order"] = self.data["global_order"]

        global_markers = serialize_markers(self.data["global_markers"])
        if global_markers:
            doc["global_markers"] = global_markers

        markers_dict = {}
        for entry in self.data["entries"]:
            val = entry["feature_value"]
            if val:
                markers_dict[val] = serialize_markers(entry["markers"])
        doc["markers"] = markers_dict

        return doc

    def insert_entry(self) -> None:
        self.data["entries"].append(
            {"uuid": str(uuid.uuid4()), "feature_value": "", "markers": []}
        )

    def remove_entry(self, e_uid: str) -> None:
        self.data["entries"] = [e for e in self.data["entries"] if e["uuid"] != e_uid]

    def add_marker(self, markers: list[Marker]) -> None:
        markers.append(Marker(value="marker value...", type="suffix"))

    def remove_marker(self, markers: list[Marker], m_uuid: str) -> None:
        markers[:] = [m for m in markers if m.uuid != m_uuid]


def feature_markers_toolbar(editor: FeatureMarkersEditor) -> None:
    col_add, col_save, col_preview_toggle, _ = st.columns([1.4, 1.2, 1.6, 5])

    with col_add:
        if st.button("➕ Add value entry", use_container_width=True):
            editor.insert_entry()
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


def feature_markers_page() -> None:
    st.set_page_config(
        page_title="Feature Markers Editor",
        page_icon="🔖",
        layout="wide",
    )

    config_dir: str = st.session_state["config_dir"]
    config_walker: ConfigWalker = st.session_state["config_walker"]
    fm_files = config_walker.config_filemap[_config_key]

    editor_sidebar(
        kind=_config_kind,
        editor_class=FeatureMarkersEditor,
        config_dir=config_dir,
        config_walker=config_walker,
        kind_files=fm_files,
        help_str=_help_str,
    )

    editor = editor_guard(kind=_config_kind)
    editor.read_form_to_state()
    editor_header(kind=_config_kind, editor=editor)

    # 1. Config section
    grammar = st.session_state.get("grammar")
    available_features = []
    available_rules = []
    available_principal_parts = []
    fm_configs = []

    if grammar:
        available_features = list(
            grammar.feature_orchestrator.feature_values_registry.features_to_values.keys()
        )
        available_rules = list(grammar.fst_orchestrator.rule_registry.data.keys())
        # Principal parts are columns in PartOfSpeech configs
        pos_reg = grammar.lexicon_registry
        pp_sets = set()
        for pos_config in pos_reg.config_objects.values():
            for col in pos_config.get("columns", []):
                pp_sets.add(col)
        available_principal_parts = sorted(list(pp_sets))
        fm_configs = sorted([Path(f).stem for f in fm_files])

    with st.expander("Configuration", expanded=not bool(editor.data["feature"])):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.selectbox(
                "Target Feature",
                options=[""] + available_features,
                index=available_features.index(editor.data["feature"]) + 1
                if editor.data["feature"] in available_features
                else 0,
                key=editor.get_widget_key(_FEATURE_PREFIX, "main"),
            )
        with col2:
            st.selectbox(
                "Inherits from",
                options=[""] + fm_configs,
                index=fm_configs.index(editor.data["inherits"]) + 1
                if editor.data["inherits"] in fm_configs
                else 0,
                key=editor.get_widget_key(_INHERITS_PREFIX, "main"),
            )
        with col3:
            st.text_input(
                "Global Order Stage",
                value=editor.data["global_order"],
                key=editor.get_widget_key(_GLOBAL_ORDER_PREFIX, "main"),
                placeholder="suffixation",
            )

        render_marker_list(
            editor.data["global_markers"],
            "global",
            editor,
            available_rules,
            available_principal_parts,
            label="Global Markers",
        )

    toolbar_placeholder = st.empty()
    st.divider()

    # 2. Entries section
    feature = editor.data["feature"]
    feature_values = []
    if grammar and feature in grammar.feature_orchestrator.feature_values_registry.features_to_values:
        feature_values = grammar.feature_orchestrator.feature_values_registry.features_to_values[feature]

    for entry in editor.data["entries"]:
        e_uid = entry["uuid"]
        with st.container(border=True):
            col_val, col_del = st.columns([4, 1])
            with col_val:
                if feature_values:
                    st.selectbox(
                        f"Value for {feature}",
                        options=[""] + feature_values,
                        index=feature_values.index(entry["feature_value"]) + 1
                        if entry["feature_value"] in feature_values
                        else 0,
                        key=editor.get_widget_key(_ENTRY_VAL_PREFIX, e_uid),
                    )
                else:
                    st.text_input(
                        "Feature Value",
                        value=entry["feature_value"],
                        key=editor.get_widget_key(_ENTRY_VAL_PREFIX, e_uid),
                        placeholder="e.g. perfective",
                    )
            with col_del:
                st.write("##")
                if st.button(
                    "✕ Remove Entry",
                    key=editor.get_widget_key(_REMOVE_ENTRY_PREFIX, e_uid),
                    use_container_width=True,
                ):
                    editor.remove_entry(e_uid)
                    st.rerun()

            render_marker_list(
                entry["markers"],
                f"entry-{e_uid}",
                editor,
                available_rules,
                available_principal_parts,
            )

    with toolbar_placeholder.container():
        feature_markers_toolbar(editor)


if __name__ == "__main__":
    feature_markers_page()
