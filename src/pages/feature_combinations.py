"""
Streamlit Feature Combinations Editor
=====================================
A UI for creating and editing feature combination YAML configs.
"""

from __future__ import annotations

import uuid
from typing import Any

import streamlit as st
import yaml

from src.config_utils.config_walker import ConfigWalker
from src.grammar.registry.feature_combination_registry import FeatureCombinationsRegistry
from src.pages.editor_utils import (
    EditorBase,
    editor_guard,
    editor_header,
    editor_sidebar,
)

_config_kind = "FeatureCombinations"
_config_key = "feature_combination_configs"

# Prefix constants
_FEATURE_LIST_PREFIX = "features-list-"
_COMBO_VAL_PREFIX = "combo-val-"
_REMOVE_COMBO_PREFIX = "remove-combo-"

_WIDGET_PREFIXES: list[str] = [
    _FEATURE_LIST_PREFIX,
    _COMBO_VAL_PREFIX,
    _REMOVE_COMBO_PREFIX,
]

_help_str = """
Feature combination files define which sets of feature values are valid together.
For example, you might define that only certain subjects can go with certain objects.
Wildcards (`*`) and comma-separated lists are supported in values.
"""


class FeatureCombinationsEditor(EditorBase):
    """
    Editor for FeatureCombinations YAML configs.

    self.data keys:
        features     — list[str] (names of features included in this config)
        combinations — list[dict] (each dict has uuid and feature values)
    """

    def __init__(self) -> None:
        super().__init__(kind=_config_kind, config_key=_config_key)

    def build_state_from_config(self, config_object: dict) -> dict:
        # We need the FeatureValuesRegistry to build the backend object,
        # though for the editor we mainly want the raw data.
        grammar = st.session_state.get("grammar")
        if grammar is None:
            # Fallback for initialization if grammar isn't loaded yet
            # but usually it is required by the app lifecycle.
            features_to_values = {}
        else:
            features_to_values = grammar.feature_orchestrator.feature_values_registry

        filepath = config_object["source_path"]
        # Dummy registry to leverage loading logic if needed, 
        # but we mostly care about the raw combinations list.
        features = config_object.get("features", [])
        raw_combos = config_object.get("combinations", [])
        
        # Add stable UUIDs for Streamlit keys
        combinations = []
        for combo in raw_combos:
            combo_with_id = {"uuid": str(uuid.uuid4())}
            for f in features:
                val = combo.get(f, "unmarked")
                # Handle lists -> comma string for UI
                if isinstance(val, list):
                    val = ", ".join(val)
                combo_with_id[f] = val
            combinations.append(combo_with_id)

        return {
            "features": features,
            "combinations": combinations,
        }

    def read_form_to_state(self) -> None:
        """Sync widget values back to self.data."""
        # 1. Update features list
        # Note: We use a multi-select in the header/top section
        selected_features = st.session_state.get(self.get_widget_key(_FEATURE_LIST_PREFIX, "main"), [])
        if selected_features:
            self.data["features"] = selected_features

        # 2. Update combinations
        features = self.data.get("features", [])
        combinations = self.data.get("combinations", [])
        
        for combo in combinations:
            uid = combo["uuid"]
            for f in features:
                val = self.get_node_widget(_COMBO_VAL_PREFIX, uid, suffix=f)
                if val is not None:
                    combo[f] = val.strip()

    def to_yaml(self) -> dict:
        features = self.data.get("features", [])
        combinations = self.data.get("combinations", [])
        
        output_combos = []
        for combo in combinations:
            cleaned_combo = {}
            for f in features:
                val = combo.get(f, "unmarked")
                # Parse comma strings back to lists if needed
                if "," in val:
                    val = [v.strip() for v in val.split(",") if v.strip()]
                cleaned_combo[f] = val
            output_combos.append(cleaned_combo)

        return {
            "kind": self.kind,
            "features": features,
            "combinations": output_combos,
        }

    def get_default_data(self) -> dict:
        return {
            "features": [],
            "combinations": [],
        }

    def insert_combination(self) -> None:
        features = self.data.get("features", [])
        new_combo = {"uuid": str(uuid.uuid4())}
        for f in features:
            new_combo[f] = "unmarked"
        self.data["combinations"].append(new_combo)

    def remove_combination(self, uid: str) -> None:
        combinations = self.data.get("combinations", [])
        self.data["combinations"] = [c for c in combinations if c["uuid"] != uid]
        # Cleanup keys
        for prefix in _WIDGET_PREFIXES:
            # This is a bit complex for suffixes, but clear_all... covers it on switch
            st.session_state.pop(f"{prefix}{uid}", None)


def _render_combination(combo: dict, features: list[str], editor: FeatureCombinationsEditor) -> None:
    uid = combo["uuid"]
    cols = st.columns([1] * len(features) + [0.4])
    
    for i, f in enumerate(features):
        with cols[i]:
            st.text_input(
                f, # Label
                key=editor.get_widget_key(_COMBO_VAL_PREFIX, uid, suffix=f),
                value=combo.get(f, "unmarked"),
                label_visibility="collapsed" if len(features) > 1 else "visible"
            )
            
    with cols[-1]:
        if st.button("✕", key=editor.get_widget_key(_REMOVE_COMBO_PREFIX, uid), help="Delete this combination"):
            editor.remove_combination(uid)
            st.rerun()


def feature_combinations_page() -> None:

    config_dir: str = st.session_state["config_dir"]
    config_walker: ConfigWalker = st.session_state["config_walker"]
    combo_files = config_walker.config_filemap[_config_key]

    editor_sidebar(
        kind=_config_kind,
        editor_class=FeatureCombinationsEditor,
        config_dir=config_dir,
        config_walker=config_walker,
        kind_files=combo_files,
        help_str=_help_str,
    )

    editor = editor_guard(kind=_config_kind)
    editor.read_form_to_state()
    # Sync from session state before rendering to catch multiselect changes
    editor_header(kind=_config_kind, editor=editor)

    # 1. Feature selection section
    grammar = st.session_state.get("grammar")
    available_features = []
    if grammar:
        available_features = list(grammar.feature_orchestrator.feature_values_registry.features_to_values.keys())
    
    current_features = editor.data.get("features", [])
    
    with st.expander("Configuration: Participating Features", expanded=not bool(current_features)):
        selected_features = st.multiselect(
            "Select features to include in this combination set",
            options=available_features or current_features,
            default=current_features,
            key=editor.get_widget_key(_FEATURE_LIST_PREFIX, "main"),
            help="Adding or removing features will update the table columns below."
        )
        if selected_features != current_features:
            st.rerun()

    toolbar_placeholder = st.empty()
    st.divider()

    # 2. Combinations table/list
    features = editor.data.get("features", [])
    combinations = editor.data.get("combinations", [])

    if not features:
        st.warning("Please select at least one feature in the configuration section above.")
    else:
        # Header row for the "table"
        cols = st.columns([1] * len(features) + [0.4])
        for i, f in enumerate(features):
            cols[i].markdown(f"**{f}**")
        
        if not combinations:
            st.info("No combinations yet. Click **➕ Add combination** to start.")
        else:
            for combo in combinations:
                _render_combination(combo, features, editor)

    with toolbar_placeholder.container():
        render_editor_toolbar(editor, add_label="Add combination", add_callback=editor.insert_combination)


if __name__ == "__main__":
    feature_combinations_page()
