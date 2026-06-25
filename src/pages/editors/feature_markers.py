"""
Streamlit Feature Markers Editor
================================
A UI for creating and editing feature marker YAML configs.
"""

from __future__ import annotations

import uuid
from typing import Any

import streamlit as st
from pathlib import Path

from src.grammar.registry.feature_marker_registry import Marker
from src.grammar.registry.feature_marker_registry import FeatureMarkers, MarkerList
from src.grammar.registry.feature_values_registry import Feature
from src.grammar import Grammar
from src.pages.editors.editor_base import EditorBase
from src.validation import validate_file_reference_str
from src.widgets import (
    render_editor_guard,
    render_editor_header,
    render_editor_sidebar,
    render_editor_toolbar,
    render_marker_list,
    sync_marker_list,
)

_config_kind = "FeatureMarkers"
_config_key = "feature_marker_configs"

# Prefix constants
_GLOBAL_ORDER_PREFIX = "global-order-"
_FEATURE_PREFIX = "feature-select-"
_INHERITS_PREFIX = "inherits-select-"
_ENTRY_VAL_PREFIX = "entry-val-"
_REMOVE_ENTRY_PREFIX = "remove-entry-"

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
        grammar: Grammar = st.session_state.get("grammar")
        feature_name = config_object.get("feature", "")
        feature = grammar.feature_orchestrator.get_feature(feature_name)
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
        self.clear_errors()
        # 1. Top-level fields
        feature_val = st.session_state.get(self.get_widget_key(_FEATURE_PREFIX, "main"))
        if feature_val is not None:
            self.data["feature"] = feature_val

        inherits_val = st.session_state.get(
            self.get_widget_key(_INHERITS_PREFIX, "main")
        )
        if inherits_val is not None:
            self.data["inherits"] = validate_file_reference_str(inherits_val)

        global_order_val = st.session_state.get(
            self.get_widget_key(_GLOBAL_ORDER_PREFIX, "main")
        )
        if global_order_val is not None:
            self.data["global_order"] = global_order_val

        # 2. Global markers
        sync_marker_list(self, self.data["global_markers"], "global")

        # 3. Entries
        for entry in self.data["entries"]:
            e_uid = entry["uuid"]
            val = self.get_node_widget(_ENTRY_VAL_PREFIX, e_uid)
            if val is not None:
                entry["feature_value"] = val
            sync_marker_list(self, entry["markers"], f"entry-{e_uid}")

    def to_yaml(self) -> dict:
        grammar = st.session_state.get("grammar")
        if grammar is None:
            st.error("Grammar not loaded. Cannot serialize feature markers.")
            st.stop()

        feature_orchestrator = grammar.feature_orchestrator
        feature_obj = feature_orchestrator.get_feature(self.data["feature"])

        data_dict = {}
        for entry in self.data["entries"]:
            val = entry["feature_value"]
            if val:
                data_dict[val] = MarkerList(entry["markers"])

        fm = FeatureMarkers(
            feature=feature_obj,
            inherits=self.data["inherits"] or None,
            data=data_dict,
            global_order=self.data["global_order"] or None,
            global_markers=MarkerList(self.data["global_markers"]),
        )
        return fm.to_dict()

    def get_default_data(self) -> dict:
        return {
            "feature": "",
            "global_order": "",
            "inherits": "",
            "global_markers": [],
            "entries": [],
        }

    def insert_entry(self) -> None:
        self.data["entries"].append(
            {"uuid": str(uuid.uuid4()), "feature_value": "", "markers": []}
        )

    def remove_entry(self, e_uid: str) -> None:
        self.data["entries"] = [e for e in self.data["entries"] if e["uuid"] != e_uid]


def feature_markers_page() -> None:
    st.set_page_config(
        page_title="Feature Markers Editor",
        page_icon="🔖",
        layout="wide",
    )

    render_editor_sidebar(
        kind=_config_kind,
        editor_class=FeatureMarkersEditor,
        config_key=_config_key,
        help_str=_help_str,
    )

    editor = render_editor_guard(kind=_config_kind)
    editor.read_form_to_state()
    render_editor_header(kind=_config_kind, editor=editor)

    # 1. Config section
    config_walker = st.session_state["config_walker"]
    fm_files = config_walker.config_filemap[_config_key]
    grammar: Grammar = st.session_state.get("grammar")
    available_features = []
    available_rules = []
    available_principal_parts = []
    fm_configs = []

    if grammar:
        available_features = sorted(
            list(grammar.feature_orchestrator.features.values())
        )
        available_rules = list(grammar.fst_orchestrator.rule_registry.data.keys())
        # Principal parts are columns in PartOfSpeech configs
        pos_reg = grammar.lexicon_registry
        pp_sets = set()
        for pos_config in pos_reg.config_objects.values():
            for col in pos_config.get("columns", []):
                pp_sets.add(col)
        available_principal_parts = sorted(list(pp_sets))
        fm_configs = sorted(
            [validate_file_reference_str(Path(f).stem) for f in fm_files]
        )

    with st.expander("Configuration", expanded=not bool(editor.data["feature"])):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.selectbox(
                "Target Feature",
                options=[""] + available_features,
                index=(
                    available_features.index(editor.data["feature"]) + 1
                    if editor.data["feature"] in available_features
                    else 0
                ),
                key=editor.get_widget_key(_FEATURE_PREFIX, "main"),
            )
        with col2:
            st.selectbox(
                "Inherits from",
                options=[""] + fm_configs,
                index=(
                    fm_configs.index(editor.data["inherits"]) + 1
                    if editor.data["inherits"] in fm_configs
                    else 0
                ),
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
            editor,
            editor.data["global_markers"],
            "global",
            available_rules,
            available_principal_parts,
            label="Global Markers",
        )

    toolbar_placeholder = st.empty()
    st.divider()

    # 2. Entries section
    feature: Feature = editor.data["feature"]

    for entry in editor.data["entries"]:
        e_uid = entry["uuid"]
        with st.container(border=True):
            col_val, col_del = st.columns([4, 1])
            with col_val:
                if feature and feature.values:
                    st.selectbox(
                        f"Value for {feature.name}",
                        options=[""] + feature.values,
                        index=(
                            feature.values.index(entry["feature_value"]) + 1
                            if entry["feature_value"] in feature.values
                            else 0
                        ),
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
                editor,
                entry["markers"],
                f"entry-{e_uid}",
                available_rules,
                available_principal_parts,
            )

    with toolbar_placeholder.container():
        render_editor_toolbar(
            editor, add_label="Add value entry", add_callback=editor.insert_entry
        )


if __name__ == "__main__":
    feature_markers_page()
