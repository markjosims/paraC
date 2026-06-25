"""
Streamlit Feature Values Editor
===============================
A UI for creating and editing feature definition YAML configs.
"""

from __future__ import annotations
import streamlit as st

from src.grammar.registry.feature_values_registry import Feature, FeatureValuesRegistry
from src.pages.editors.editor_base import EditorBase
from src.widgets import (
    render_editor_guard,
    render_editor_header,
    render_editor_sidebar,
    render_editor_toolbar,
    validated_text_input,
)
from src.validation import validate_feature_name, validate_feature_values

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
        self.clear_errors()
        id_map: dict[str, Feature] = self.data.get("id_map", {})
        for uid, feature in id_map.items():
            name_val = self.get_node_widget(_NAME_PREFIX, uid)
            if name_val is not None:
                name_val = name_val.strip()
                validate_feature_name(self.add_error, name_val, uid, id_map)
                feature.name = name_val

            # Read individual values
            new_values = []
            idx = 0
            while True:
                val = self.get_node_widget(_VALUE_ITEM_PREFIX, uid, suffix=str(idx))
                if val is None:
                    break
                val = val.strip()
                if val:
                    new_values.append(val)
                idx += 1

            if idx > 0:
                if not new_values:
                    self.add_error(
                        f"Feature '{feature.name}': Must have at least one value."
                    )
                if "unmarked" not in new_values:
                    new_values.append("unmarked")
                feature.values = new_values

    def to_yaml(self) -> dict:
        """
        Serialize to FeatureDefinitions YAML format.
        """
        features: list[Feature] = self.data.get("features", [])
        registry = FeatureValuesRegistry(data={f.name: f for f in features})
        return registry.to_dict()

    def get_default_data(self) -> dict:
        return {
            "features": [],
            "id_map": {},
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
            feature.values.insert(
                len(feature.values) - 1, f"value_{len(feature.values)}"
            )
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

    with st.expander(
        f"Feature: `{feature.name}`",
        expanded=True,
        key=editor.get_widget_key("expander-", uid),
    ):
        col_name, col_remove = st.columns([4, 1])
        with col_name:
            validated_text_input(
                editor,
                "Feature Name",
                _NAME_PREFIX,
                uid,
                value=feature.name,
                placeholder="tam",
                validation_fn=lambda v, add_error: validate_feature_name(
                    add_error, v, uid, editor.data.get("id_map", {})
                ),
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
                validated_text_input(
                    editor,
                    f"Value {i + 1}",
                    _VALUE_ITEM_PREFIX,
                    uid,
                    value=val,
                    suffix=str(i),
                    label_visibility="collapsed",
                    validation_fn=(
                        lambda v, add_error: (
                            validate_feature_values(add_error, v, feature.name)
                            if i == 0
                            else None
                        )
                    ),
                )
            with d_col:
                if st.button(
                    "✕",
                    key=editor.get_widget_key("del-val-", uid, suffix=str(i)),
                    help="Delete this value",
                ):
                    editor.remove_value(uid, i)
                    st.rerun()

        st.button(
            "➕ Add value",
            key=editor.get_widget_key("add-val-", uid),
            on_click=editor.add_value,
            args=(uid,),
        )


def feature_values_page() -> None:
    """Main page function for the Feature Values editor."""
    st.set_page_config(
        page_title="Feature Values Editor",
        page_icon="🏷️",
        layout="wide",
    )

    render_editor_sidebar(
        kind=_config_kind,
        editor_class=FeatureValuesEditor,
        config_key=_config_key,
        help_str=_help_str,
    )

    editor = render_editor_guard(kind=_config_kind)
    editor.read_form_to_state()
    render_editor_header(kind=_config_kind, editor=editor)

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
        render_editor_toolbar(
            editor, add_label="Add feature", add_callback=editor.insert_feature
        )


if __name__ == "__main__":
    feature_values_page()
