"""
Streamlit Contingent Markers Editor
===================================
A UI for creating and editing contingent feature marker YAML configs.
"""

from __future__ import annotations

import uuid
from typing import Any

import streamlit as st

from src.grammar import Grammar
from src.grammar.registry.feature_values_registry import Feature
from src.grammar.orchestrator.feature_orchestrator import FeatureOrchestrator
from src.grammar.registry.feature_marker_registry import Marker
from src.pages.editors.editor_base import EditorBase
from src.grammar.registry.contingent_marker_registry import ContingentMarkers
from src.grammar.registry.feature_marker_registry import MarkerList
from src.widgets import (
    render_feature_multiselect,
    render_editor_guard,
    render_editor_header,
    render_editor_sidebar,
    render_editor_toolbar,
    render_marker_list,
    sync_marker_list,
)

_config_kind = "ContingentFeatureMarkers"
_config_key = "contingent_feature_marker_configs"

# Prefix constants
_GLOBAL_ORDER_PREFIX = "global-order-"
_FEATURE_LIST_PREFIX = "features-list-"
_ENTRY_VAL_PREFIX = "entry-val-"
_REMOVE_ENTRY_PREFIX = "remove-entry-"

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
        """
        Instantiate all global and feature markers to `Marker` class objects,
        instantiate features to `Feature` class objects and load global order.
        """
        global_order = config_object.get("global_order", "")

        grammar: Grammar = st.session_state.grammar
        feature_orchestrator: FeatureOrchestrator = grammar.feature_orchestrator
        feature_names = config_object.get("features", [])
        features = [
            feature_orchestrator.get_feature(feature_name)
            for feature_name in feature_names
        ]

        def load_markers(raw: Any) -> list[Marker]:
            if not raw:
                return []
            if isinstance(raw, dict):
                raw = [raw]
            return [Marker.from_config(m) for m in raw]

        global_markers = load_markers(config_object.get("global_markers", []))

        markers_raw = config_object.get("markers", [])
        entries = []
        for entry_config in markers_raw:
            f_vec = entry_config.get("features", {})
            entries.append(
                {
                    "uuid": str(uuid.uuid4()),
                    "features": f_vec,
                    "realization": load_markers(entry_config.get("realization", [])),
                }
            )

        return {
            "features": sorted(features),
            "global_order": global_order,
            "global_markers": global_markers,
            "entries": entries,
        }

    def read_form_to_state(self) -> None:
        """Sync widget values back to self.data."""
        self.clear_errors()
        # 1. Top-level fields
        # features are updated via feature_multiselect callback

        g_order = st.session_state.get(
            self.get_widget_key(_GLOBAL_ORDER_PREFIX, "main")
        )
        if g_order is not None:
            self.data["global_order"] = g_order

        # 2. Global markers
        sync_marker_list(self, self.data["global_markers"], "global")

        # 3. Entries
        for entry in self.data["entries"]:
            uid = entry["uuid"]
            for f in self.data["features"]:
                val = self.get_node_widget(_ENTRY_VAL_PREFIX, uid, suffix=f.name)
                if val is not None:
                    entry["features"][f.name] = val.strip()

            sync_marker_list(self, entry["realization"], f"entry-{uid}")

    def to_yaml(self) -> dict:
        features: list[Feature] = self.data["features"]
        feature_mappings = {}
        feature_names = [f.name for f in features]
        for entry in self.data["entries"]:
            # Only include participating features that have a non-empty, non-unmarked value
            clean_vec = {
                k: v
                for k, v in entry["features"].items()
                if k in feature_names and v and v != "unmarked"
            }
            if not clean_vec:
                continue

            vector = frozenset(clean_vec.items())
            feature_mappings[vector] = MarkerList(entry["realization"])

        cm = ContingentMarkers(
            features=features,
            feature_mappings=feature_mappings,
            global_order=self.data["global_order"] or None,
            global_markers=MarkerList(self.data["global_markers"]),
        )
        return cm.to_dict()

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
    features: list[Feature],
    editor: ContingentMarkersEditor,
    available_rules: list[str],
    available_principal_parts: list[str],
) -> None:
    uid = entry["uuid"]
    with st.container(border=True):
        cols = st.columns([1] * len(features) + [0.4])
        for i, f in enumerate(features):
            with cols[i]:
                f_vals = f.values
                options = ["unmarked"] + sorted(f_vals)
                current_val = entry["features"].get(f.name, "unmarked")
                if current_val not in options:
                    options.append(current_val)

                st.selectbox(
                    f.name,
                    options=options,
                    index=options.index(current_val),
                    key=editor.get_widget_key(_ENTRY_VAL_PREFIX, uid, suffix=f.name),
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
            editor,
            entry["realization"],
            f"entry-{uid}",
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

    render_editor_sidebar(
        kind=_config_kind,
        editor_class=ContingentMarkersEditor,
        config_key=_config_key,
        help_str=_help_str,
    )

    editor = render_editor_guard(kind=_config_kind)
    editor.read_form_to_state()
    render_editor_header(kind=_config_kind, editor=editor)

    grammar: Grammar = st.session_state.grammar
    available_rules = []
    available_principal_parts = []
    if grammar:
        available_rules = list(grammar.fst_orchestrator.rule_registry.data.keys())
        pp_sets = set()
        for pos_config in grammar.lexicon_registry.config_objects.values():
            for col in pos_config.get("columns", []):
                pp_sets.add(col)
        available_principal_parts = sorted(list(pp_sets))

    # 1. Config section
    current_features = editor.data.get("features", [])
    with st.expander("Configuration", expanded=not bool(current_features)):
        render_feature_multiselect(
            "Participating Features",
            editor,
            _FEATURE_LIST_PREFIX,
            help_str="Features that define the contingencies.",
        )

        st.text_input(
            "Global Order Stage",
            value=editor.data["global_order"],
            key=editor.get_widget_key(_GLOBAL_ORDER_PREFIX, "main"),
            placeholder="argument_marking",
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
    features: list[Feature] = editor.data.get("features", [])
    if not features:
        st.warning("Please select at least one participating feature above.")
    else:
        # Table Header
        cols = st.columns([1] * len(features) + [0.4])
        for i, feature in enumerate(features):
            cols[i].markdown(f"**{feature.name}**")

        for entry in editor.data["entries"]:
            _render_entry(
                entry,
                features,
                editor,
                available_rules,
                available_principal_parts,
            )

    with toolbar_placeholder.container():
        render_editor_toolbar(
            editor, add_label="Add entry", add_callback=editor.insert_entry
        )


if __name__ == "__main__":
    contingent_markers_page()
