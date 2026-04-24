"""
Streamlit Feature Values Editor
===============================
A UI for creating and editing feature definition YAML configs.
"""

from __future__ import annotations

from typing import Any

import streamlit as st
import yaml

from src.config_utils.config_walker import ConfigWalker
from src.grammar.registry.feature_values_registry import Feature, FeatureValuesRegistry
from src.pages.editor_utils import (
    EditorBase,
    editor_guard,
    editor_header,
    editor_sidebar,
)

_config_kind = "FeatureDefinitions"
_config_key = "feature_definition_configs"

_NAME_PREFIX = "name-"
_VALUE_ITEM_PREFIX = "value_item-"
_REMOVE_PREFIX = "remove-"
_WIDGET_PREFIXES: list[str] = [
    _NAME_PREFIX,
    _VALUE_ITEM_PREFIX,
    _REMOVE_PREFIX,
]

_help_str = """
This editor allows you to define features (either morphological or lexical)
and their possible values.
"""

class FeatureValuesEditor(EditorBase):
    """
    Editor for FeatureDefinitions YAML configs.

    self.data keys:
        features — list[Feature]
        id_map   — dict[uuid, Feature]
    """

    def __init__(self) -> None:
        super().__init__(kind=_config_kind, config_key=_config_key)

    def build_state_from_config(self, config_object: dict) -> dict:
        filepath = config_object["source_path"]
        registry = FeatureValuesRegistry(config_objects={filepath: config_object})
        features = list(registry.data.values())
        id_map = {f.uuid: f for f in features}
        return {
            "features": features,
            "id_map": id_map,
        }

    def read_form_to_state(self) -> None:
        """
        Sync widget values from st.session_state back into Feature objects.
        """
        id_map: dict[str, Feature] = self.data.get("id_map", {})
        for uid, feature in id_map.items():
            name_val = self.get_node_widget(_NAME_PREFIX, uid)
            if name_val is not None:
                feature.name = name_val

            # Read individual values
            new_values = []
            idx = 0
            while True:
                val = self.get_node_widget(_VALUE_ITEM_PREFIX, uid, suffix=str(idx))
                if val is None:
                    # Check if we have more values in the model than in widgets
                    # (this can happen if we haven't rendered them yet)
                    break
                if val.strip():
                    new_values.append(val.strip())
                idx += 1
            
            # If we didn't find any widgets (e.g. first load or reset), 
            # don't overwrite the model with an empty list
            if idx > 0:
                if "unmarked" not in new_values:
                    new_values.append("unmarked")
                feature.values = new_values

    def to_yaml(self) -> dict:
        """
        Serialize to FeatureDefinitions YAML format.
        """
        features: list[Feature] = self.data.get("features", [])
        features_dict = {}
        for f in features:
            # strip "unmarked" for storage to stay consistent with auto-generation logic
            clean_values = [v for v in f.values if v != "unmarked"]
            features_dict[f.name] = clean_values

        return {
            "kind": self.kind,
            "features": features_dict,
        }

    def insert_feature(self) -> str:
        """Append a blank feature; return its uuid."""
        new_feature = Feature(name="new_feature", values=["value1"])
        self.data["id_map"][new_feature.uuid] = new_feature
        self.data["features"].append(new_feature)
        return new_feature.uuid

    def remove_feature(self, uid: str) -> Feature:
        """Remove feature by uuid, clear its widget keys."""
        feature = self.data["id_map"].pop(uid)
        self.data["features"].remove(feature)
        for prefix in _WIDGET_PREFIXES:
            # Note: this doesn't clear the indexed value_item keys
            # because we don't know the count here easily. 
            # clear_all_editor_widget_keys handles it better on page switch.
            st.session_state.pop(f"{prefix}{uid}", None)
        return feature

    def add_value(self, uid: str) -> None:
        """Add a placeholder value to a feature."""
        feature = self.data["id_map"][uid]
        # Insert at end but before "unmarked"
        if "unmarked" in feature.values:
            feature.values.insert(len(feature.values) - 1, f"value_{len(feature.values)}")
        else:
            feature.values.append(f"value_{len(feature.values) + 1}")

    def remove_value(self, uid: str, index: int) -> None:
        """Remove a value by display index (skipping unmarked)."""
        feature = self.data["id_map"][uid]
        display_values = [v for v in feature.values if v != "unmarked"]
        if 0 <= index < len(display_values):
            val_to_remove = display_values[index]
            feature.values.remove(val_to_remove)


def _render_feature(uid: str, editor: FeatureValuesEditor) -> None:
    """Render a single feature entry as an expandable card."""
    feature: Feature = editor.data["id_map"][uid]
    # Filter "unmarked" for user-facing field to avoid confusion
    display_values = [v for v in feature.values if v != "unmarked"]

    with st.expander(f"Feature: `{feature.name}`", expanded=True):
        col_name, col_remove = st.columns([4, 1])
        with col_name:
            st.text_input(
                "Feature Name",
                key=editor.get_widget_key(_NAME_PREFIX, uid),
                value=feature.name,
                placeholder="tam",
            )
        with col_remove:
            st.write("##")  # alignment
            if st.button(
                "✕ Delete Feature",
                key=editor.get_widget_key(_REMOVE_PREFIX, uid),
                use_container_width=True,
            ):
                editor.remove_feature(uid)
                st.rerun()

        st.text("Values")
        for i, val in enumerate(display_values):
            v_col, d_col = st.columns([4, 4])
            with v_col:
                st.text_input(
                    f"Value {i+1}",
                    key=editor.get_widget_key(_VALUE_ITEM_PREFIX, uid, suffix=str(i)),
                    value=val,
                    label_visibility="collapsed",
                )
            with d_col:
                if st.button("✕", key=editor.get_widget_key("del-val-", uid, suffix=str(i)), help="Delete this value"):
                    editor.remove_value(uid, i)
                    st.rerun()
        
        if st.button("➕ Add value", key=editor.get_widget_key("add-val-", uid)):
            editor.add_value(uid)
            st.rerun()


def feature_values_toolbar(editor: FeatureValuesEditor) -> None:
    """Toolbar for adding features and saving YAML."""
    col_add, col_save, col_preview_toggle, _ = st.columns([1.4, 1.2, 1.6, 5])

    with col_add:
        if st.button("➕ Add feature", use_container_width=True):
            editor.insert_feature()
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


def feature_values_page() -> None:
    """Main page function for the Feature Values editor."""
    st.set_page_config(
        page_title="Feature Values Editor",
        page_icon="🏷️",
        layout="wide",
    )

    config_dir: str = st.session_state["config_dir"]
    config_walker: ConfigWalker = st.session_state["config_walker"]
    feature_files = config_walker.config_filemap[_config_key]

    editor_sidebar(
        kind=_config_kind,
        editor_class=FeatureValuesEditor,
        config_dir=config_dir,
        config_walker=config_walker,
        kind_files=feature_files,
        help_str=_help_str,
    )

    editor = editor_guard(kind=_config_kind)
    editor.read_form_to_state()
    editor_header(kind=_config_kind, editor=editor)

    toolbar_placeholder = st.empty()
    st.divider()

    id_map = editor.data.get("id_map", {})
    if not id_map:
        st.info("No features yet. Click **➕ Add feature** to start.")
    else:
        # Use list of keys to avoid mutation issues
        for uid in list(id_map.keys()):
            _render_feature(uid, editor)

    with toolbar_placeholder.container():
        feature_values_toolbar(editor)


if __name__ == "__main__":
    feature_values_page()
