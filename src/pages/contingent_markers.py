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
    render_editor_toolbar,
    MARKER_WIDGET_PREFIXES,
)

_config_kind = "ContingentFeatureMarkers"
_config_key = "contingent_feature_marker_configs"

# Prefix constants
_GLOBAL_ORDER_PREFIX = "global-order-"
_FEATURE_LIST_PREFIX = "features-list-"
_ENTRY_VAL_PREFIX = "entry-val-"
_REMOVE_ENTRY_PREFIX = "remove-entry-"

_WIDGET_PREFIXES: list[str] = [
    _GLOBAL_ORDER_PREFIX,
    _FEATURE_LIST_PREFIX,
    _ENTRY_VAL_PREFIX,
    _REMOVE_ENTRY_PREFIX,
] + MARKER_WIDGET_PREFIXES

_help_str = """
Contingent marker files define realizations contingent on feature vectors.
- **Features**: Select the features that participate in these contingencies.
- **Markers**: Map specific combinations of feature values to realizations.
"""


class ContingentMarkersEditor(EditorBase):
    """
    Editor for ContingentFeatureMarkers YAML configs.

    self.data keys:
        features       — list[str] (participating features)
        global_order   — str
        global_markers — list[Marker]
        entries        — list[dict] (uuid, features: dict[str, str], realization: list[Marker])
    """

    def __init__(self) -> None:
        super().__init__(kind=_config_kind, config_key=_config_key)

    def build_state_from_config(self, config_object: dict) -> dict:
        global_order = config_object.get("global_order", "")

        def load_markers(raw: Any) -> list[Marker]:
            if not raw:
                return []
            if isinstance(raw, dict):
                raw = [raw]
            return [Marker.from_config(m) for m in raw]

        global_markers = load_markers(config_object.get("global_markers", []))

        markers_raw = config_object.get("markers", [])
        features_set = set()
        entries = []
        for entry_config in markers_raw:
            f_vec = entry_config.get("features", {})
            features_set.update(f_vec.keys())
            entries.append(
                {
                    "uuid": str(uuid.uuid4()),
                    "features": f_vec,
                    "realization": load_markers(entry_config.get("realization", [])),
                }
            )

        return {
            "features": sorted(list(features_set)),
            "global_order": global_order,
            "global_markers": global_markers,
            "entries": entries,
        }

    def read_form_to_state(self) -> None:
        """Sync widget values back to self.data."""
        # 1. Top-level fields
        selected_features = st.session_state.get(
            self.get_widget_key(_FEATURE_LIST_PREFIX, "main"), []
        )
        if selected_features:
            self.data["features"] = selected_features

        g_order = st.session_state.get(self.get_widget_key(_GLOBAL_ORDER_PREFIX, "main"))
        if g_order is not None:
            self.data["global_order"] = g_order

        # 2. Global markers
        self._sync_marker_list(self.data["global_markers"], "global")

        # 3. Entries
        for entry in self.data["entries"]:
            uid = entry["uuid"]
            for f in self.data["features"]:
                val = self.get_node_widget(_ENTRY_VAL_PREFIX, uid, suffix=f)
                if val is not None:
                    entry["features"][f] = val.strip()

            self._sync_marker_list(entry["realization"], f"entry-{uid}")

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
        }
        if self.data["global_order"]:
            doc["global_order"] = self.data["global_order"]

        global_markers = serialize_markers(self.data["global_markers"])
        if global_markers:
            doc["global_markers"] = global_markers

        markers_list = []
        for entry in self.data["entries"]:
            # Only include participating features
            clean_vec = {
                k: v
                for k, v in entry["features"].items()
                if k in self.data["features"] and v
            }
            if not clean_vec:
                continue

            realization = serialize_markers(entry["realization"])
            markers_list.append({"features": clean_vec, "realization": realization})

        doc["markers"] = markers_list
        return doc

    def get_default_data(self) -> dict:
        return {
            "features": [],
            "global_order": "",
            "global_markers": [],
            "entries": [],
        }

    def insert_entry(self) -> None:
        self.data["entries"].append(
            {"uuid": str(uuid.uuid4()), "features": {}, "realization": []}
        )

    def remove_entry(self, uid: str) -> None:
        self.data["entries"] = [e for e in self.data["entries"] if e["uuid"] != uid]

    def add_marker(self, markers: list[Marker]) -> None:
        markers.append(Marker(value="", type="suffix"))

    def remove_marker(self, markers: list[Marker], m_uuid: str) -> None:
        markers[:] = [m for m in markers if m.uuid != m_uuid]


def _render_entry(
    entry: dict,
    features: list[str],
    editor: ContingentMarkersEditor,
    available_rules: list[str],
    available_principal_parts: list[str],
) -> None:
    uid = entry["uuid"]
    with st.container(border=True):
        cols = st.columns([1] * len(features) + [0.4])
        for i, f in enumerate(features):
            with cols[i]:
                st.text_input(
                    f,
                    key=editor.get_widget_key(_ENTRY_VAL_PREFIX, uid, suffix=f),
                    value=entry["features"].get(f, "unmarked"),
                    label_visibility="collapsed" if len(features) > 1 else "visible",
                )
        with cols[-1]:
            if st.button(
                "✕",
                key=editor.get_widget_key(_REMOVE_ENTRY_PREFIX, uid),
                help="Delete entry",
            ):
                editor.remove_entry(uid)
                st.rerun()

        render_marker_list(
            entry["realization"],
            f"entry-{uid}",
            editor,
            available_rules,
            available_principal_parts,
            label="Realization",
        )


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
        available_features = list(
            grammar.feature_orchestrator.feature_values_registry.features_to_values.keys()
        )
        available_rules = list(grammar.fst_orchestrator.rule_registry.data.keys())
        pp_sets = set()
        for pos_config in grammar.lexicon_registry.config_objects.values():
            for col in pos_config.get("columns", []):
                pp_sets.add(col)
        available_principal_parts = sorted(list(pp_sets))

    # 1. Config section
    current_features = editor.data.get("features", [])
    with st.expander("Configuration", expanded=not bool(current_features)):
        st.multiselect(
            "Participating Features",
            options=available_features or current_features,
            default=current_features,
            key=editor.get_widget_key(_FEATURE_LIST_PREFIX, "main"),
            help="Features that define the contingencies.",
        )

        st.text_input(
            "Global Order Stage",
            value=editor.data["global_order"],
            key=editor.get_widget_key(_GLOBAL_ORDER_PREFIX, "main"),
            placeholder="argument_marking",
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
    features = editor.data.get("features", [])
    if not features:
        st.warning("Please select at least one participating feature above.")
    else:
        # Table Header
        cols = st.columns([1] * len(features) + [0.4])
        for i, f in enumerate(features):
            cols[i].markdown(f"**{f}**")

        for entry in editor.data["entries"]:
            _render_entry(
                entry, features, editor, available_rules, available_principal_parts
            )

    with toolbar_placeholder.container():
        render_editor_toolbar(
            editor, add_label="Add entry", add_callback=editor.insert_entry
        )


if __name__ == "__main__":
    contingent_markers_page()
