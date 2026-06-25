"""
Streamlit Feature Combinations Editor
=====================================
A UI for creating and editing feature combination YAML configs.
"""

from __future__ import annotations

import uuid
import streamlit as st

from src.grammar import Grammar
from src.grammar.registry.feature_combination_registry import FeatureValueCombinations
from src.grammar.registry.feature_values_registry import Feature
from src.pages.editors.editor_base import EditorBase
from src.widgets import (
    render_editor_guard,
    render_editor_header,
    render_editor_sidebar,
    render_editor_toolbar,
    render_feature_multiselect,
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
        features     — list[Feature] (Feature objects included in this config)
        combinations — list[dict] (each dict has uuid and feature values with string keys)
    """

    def __init__(self) -> None:
        super().__init__(kind=_config_kind, config_key=_config_key)

    def build_state_from_config(self, config_object: dict) -> dict:
        grammar: Grammar = st.session_state.grammar
        feature_orchestrator = grammar.feature_orchestrator

        feature_names = config_object.get("features", [])
        features = [feature_orchestrator.get_feature(fn) for fn in feature_names]
        raw_combos = config_object.get("combinations", [])

        # Add stable UUIDs for Streamlit keys
        combinations = []
        for combo in raw_combos:
            combo_with_id = {"uuid": str(uuid.uuid4())}
            for f in feature_names:
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
        # features are updated via feature_multiselect callback

        # 2. Update combinations
        features = self.data.get("features", [])
        combinations = self.data.get("combinations", [])

        for combo in combinations:
            uid = combo["uuid"]
            for f in features:
                val = self.get_node_widget(_COMBO_VAL_PREFIX, uid, suffix=f.name)
                if val is not None:
                    combo[f.name] = val.strip()

    def to_yaml(self) -> dict:
        grammar: Grammar = st.session_state.grammar
        if grammar is None:
            st.error("Grammar not loaded. Cannot serialize feature combinations.")
            st.stop()

        features: list[Feature] = self.data.get("features", [])
        combinations = self.data.get("combinations", [])

        output_combos = []
        for combo in combinations:
            cleaned_combo = {}
            for f in features:
                val = combo.get(f.name, "unmarked")
                # Parse comma strings back to lists if needed
                if "," in val:
                    val = [v.strip() for v in val.split(",") if v.strip()]
                cleaned_combo[f.name] = val
            output_combos.append(cleaned_combo)

        fvc = FeatureValueCombinations(
            combinations=output_combos,
            features=features,
        )
        return fvc.to_dict()

    def get_default_data(self) -> dict:
        return {
            "features": [],
            "combinations": [],
        }

    def insert_combination(self) -> None:
        features = self.data.get("features", [])
        new_combo = {"uuid": str(uuid.uuid4())}
        for f in features:
            new_combo[f.name] = "unmarked"
        self.data["combinations"].append(new_combo)

    def remove_combination(self, uid: str) -> None:
        combinations = self.data.get("combinations", [])
        self.data["combinations"] = [c for c in combinations if c["uuid"] != uid]
        # Cleanup keys
        for prefix in _WIDGET_PREFIXES:
            # This is a bit complex for suffixes, but clear_all... covers it on switch
            st.session_state.pop(f"{prefix}{uid}", None)


def _render_combination(
    combo: dict,
    features: list[Feature],
    editor: FeatureCombinationsEditor,
) -> None:
    uid = combo["uuid"]
    cols = st.columns([1] * len(features) + [0.4])

    for i, f in enumerate(features):
        with cols[i]:
            f_vals = f.values
            options = ["unmarked", "*"] + sorted(f_vals)
            current_val = combo.get(f.name, "unmarked")
            if current_val not in options:
                options.append(current_val)

            st.selectbox(
                f.name,  # Label
                options=options,
                index=options.index(current_val),
                key=editor.get_widget_key(_COMBO_VAL_PREFIX, uid, suffix=f.name),
                label_visibility="collapsed" if len(features) > 1 else "visible",
            )

    with cols[-1]:
        if st.button(
            "✕",
            key=editor.get_widget_key(_REMOVE_COMBO_PREFIX, uid),
            help="Delete this combination",
        ):
            editor.remove_combination(uid)
            st.rerun()


def feature_combinations_page() -> None:

    render_editor_sidebar(
        kind=_config_kind,
        editor_class=FeatureCombinationsEditor,
        config_key=_config_key,
        help_str=_help_str,
    )

    editor = render_editor_guard(kind=_config_kind)
    editor.read_form_to_state()
    # Sync from session state before rendering to catch multiselect changes
    render_editor_header(kind=_config_kind, editor=editor)

    # 1. Feature selection section
    grammar: Grammar = st.session_state.grammar
    current_features = editor.data.get("features", [])

    with st.expander(
        "Configuration: Participating Features", expanded=not bool(current_features)
    ):
        render_feature_multiselect(
            "Select features to include in this combination set",
            editor,
            _FEATURE_LIST_PREFIX,
            help_str="Adding or removing features will update the table columns below.",
        )

    toolbar_placeholder = st.empty()
    st.divider()

    # 2. Combinations table/list
    features = editor.data.get("features", [])
    combinations = editor.data.get("combinations", [])

    if not features:
        st.warning(
            "Please select at least one feature in the configuration section above."
        )
    else:
        # Header row for the "table"
        cols = st.columns([1] * len(features) + [0.4])
        for i, f in enumerate(features):
            cols[i].markdown(f"**{f.name}**")

        if not combinations:
            st.info("No combinations yet. Click **➕ Add combination** to start.")
        else:
            for combo in combinations:
                _render_combination(combo, features, editor)

    with toolbar_placeholder.container():
        render_editor_toolbar(
            editor, add_label="Add combination", add_callback=editor.insert_combination
        )


if __name__ == "__main__":
    feature_combinations_page()
