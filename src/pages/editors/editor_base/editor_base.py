from __future__ import annotations

import yaml
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any
from loguru import logger

import streamlit as st
from camel_converter import to_snake

from src.config_utils.schema_validation import ConfigKindType
from src.config_utils.config_walker import ConfigWalker

EDITOR_WIDGET_PREFIX = "editor-widget-"

"""
EditorBase abstract class.
"""


class EditorBase(ABC):
    """
    Abstract base class for YAML config editors.

    Subclasses implement the four abstract methods to handle the
    editor-specific data model.  The base provides concrete load/save
    orchestration that delegates to those methods.

    Instances are stored directly in st.session_state["editor"].
    """

    kind: ConfigKindType
    config_key: str
    config_walker: ConfigWalker
    path: str
    config_dir: str
    data: dict
    errors: list[str]
    field_errors: dict[str, str]

    def __init__(self, kind: ConfigKindType, config_key: str) -> None:
        """
        Args:
            kind:       The config kind string, e.g. "Inventory".
            config_key: The key used in ConfigWalker.config_data,
                        e.g. "inventory_configs".
        """
        config_walker = st.session_state.get("config_walker")
        if config_walker is None:
            raise RuntimeError("ConfigWalker not found in session state.")

        self.kind = kind
        self.config_key = config_key
        self.config_walker = config_walker
        self.path: str = ""
        self.config_dir: str = str(config_walker.config_dir)
        self.data: dict = {}
        self.errors: list[str] = []
        self.field_errors: dict[str, str] = {}

    def clear_errors(self) -> None:
        """Clear the error list and field errors."""
        self.errors = []
        self.field_errors = {}

    def add_error(self, message: str) -> None:
        """Add a validation error message."""
        if message not in self.errors:
            self.errors.append(message)

    @property
    def is_valid(self) -> bool:
        """Check if the editor state is valid (no global or field errors)."""
        return not self.errors and not self.field_errors

    @property
    def fields_are_valid(self) -> bool:
        """Check if form state is valid (no field errors)"""
        return not self.field_errors

    @property
    def subdir(self) -> str:
        """Subdirectory name for this kind, derived via to_snake(kind)."""
        return to_snake(self.kind)

    @property
    def stem(self) -> str:
        """file_name stem of the loaded file, or '' for new files."""
        return Path(self.path).stem if self.path else ""

    @property
    def scope(self) -> str:
        """Scope string for widget keys, derived from kind and filename."""
        stem = self.stem or "new"
        return f"{to_snake(self.kind)}-{stem}"

    def get_widget_key(self, prefix: str, widget_id: str, suffix: str = "") -> str:
        """
        Build a Streamlit widget key with the format:
        "editor-widget-{prefix}-{widget_id}-{suffix}"
        The suffix is optional and can be used to distinguish related widgets.
        """
        key = f"{EDITOR_WIDGET_PREFIX}-{self.scope}-{prefix}-{widget_id}"
        if suffix:
            key += f"-{suffix}"
        return key

    def get_node_widget(
        self, prefix: str, node_id: str, suffix: str = ""
    ) -> str | None:
        """
        Get the value of a widget for a given node_id and widget type, or None if not set.
        """
        key = self.get_widget_key(prefix, node_id, suffix)
        widget_value = st.session_state.get(key)
        return widget_value

    def get_numbered_widgets_for_node(
        self, prefix: str, node_id: str
    ) -> list[str] | None:
        """
        Get all widget values for a give node_id and widget type where a widget stores
        a list of values for the same widget type.
        """
        i = 0
        widget_values = []
        while True:
            widget_value = self.get_node_widget(prefix, node_id, suffix=str(i))
            if widget_value is None:
                break
            i += 1
            widget_values.append(widget_value)
        if widget_values:
            return widget_values
        return None

    """
    Abstract interface: subclasses must implement
    """

    @abstractmethod
    def build_state_from_config(self, config_object: dict) -> dict:
        """
        Parse a raw config dict (as returned by ConfigWalker) into the
        editor's working data dict.  Use backend Registry classes here;
        do not re-parse YAML manually.

        Returns the new value for self.data.
        """

    @abstractmethod
    def read_form_to_state(self) -> None:
        """
        Pull widget values from st.session_state back into model objects
        in self.data.  Called by save() before serialization.
        """

    @abstractmethod
    def to_yaml(self) -> dict:
        """
        Serialize self.data to a YAML-serializable dict (the full
        document, including top-level 'kind' and 'data' keys).
        Delegate to model .to_dict() methods where possible.
        """

    @abstractmethod
    def get_default_data(self) -> dict:
        """Return a dictionary matching the schema for an empty file of this kind."""

    """
    File lifecycle helpers
    """

    def load_file(self, filepath: str) -> None:
        """Clear widget state, then load and parse the given file."""

        logger.info(f"Loading {self.kind} file: {filepath}")

        config_object = self.config_walker.config_data[self.config_key][filepath]
        self.data = self.build_state_from_config(config_object)
        self.path = filepath

        # reset file name widget
        st.session_state["file_name"] = self.stem

    def new_file(self) -> None:
        """Reset to a blank state matching the expected schema."""
        self.data = self.get_default_data()
        self.path = ""
        st.session_state["file_name"] = ""

    def resolve_save_path(self, stem: str) -> Path:
        """Build the full save path: config_dir / subdir / stem.yaml."""
        if not stem:
            raise ValueError("File name cannot be empty.")
        if not self.config_dir:
            raise ValueError("No config directory set — open a file first.")
        return Path(self.config_dir) / self.subdir / f"{stem}.yaml"

    def save(self, stem: str) -> None:
        """
        Sync form → model, serialize to YAML, and write to the kind's subdirectory.
        Updates self.path to the written location.
        """
        dest = self.resolve_save_path(stem)
        yaml_doc = self.to_yaml()

        # Clean the dictionary to remove illicit nulls/empty strings before saving
        yaml_doc = prune_config_dict(yaml_doc, self.kind)

        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("w", encoding="utf-8") as f:
            yaml.dump(yaml_doc, f, allow_unicode=True, sort_keys=False)
        self.path = str(dest)


"""
Editor form data lifecycle helpers.
- prune_config_dict:
    Remove any null form data, excepting some keys (like a FeatureMarker)
    which may be stored in YAML backend as `null`. Called before serializing
    form data to YAML for writing to disk or for previewing.
- clear_all_editor_widget_keys:
    Remove any session state keys related to form data. Ensures clean handoff
    when switching files.
"""


def prune_config_dict(data: Any, kind: str) -> Any:
    """
    Recursively remove None values and empty strings from a dictionary,
    unless they are explicitly allowed ("licit nulls") by the schema.
    """
    # Define keys that are allowed to be null for specific kinds
    # Format: {Kind: {ParentKey: {LicitNullKey}}} or just {Kind: {LicitNullKey}}
    # We use a set of strings for simple path-based matching
    LICIT_PATHS = {
        "FeatureMarkers": {"markers"},  # markers is a dict, values can be null
        "Paradigm": {
            "feature_markers"
        },  # feature_markers is a dict, values can be null
        "Rules": {"input_pattern", "output_pattern"},
        "MorphemeSet": {"morpheme"},
    }

    kind_licit = LICIT_PATHS.get(kind, set())

    if isinstance(data, dict):
        new_dict = {}
        for k, v in data.items():
            # If the value is a licit null, keep it
            if v is None and k in kind_licit:
                new_dict[k] = v
                continue

            # Recurse
            pruned_v = prune_config_dict(v, kind)

            # Pruning logic:
            # 1. Skip None or empty string
            # 2. Skip empty dictionaries (unless they are a licit path root)
            if pruned_v in (None, ""):
                continue

            # Special case: don't prune empty lists if the schema expects them
            # (e.g. lexical_features: [])
            if pruned_v == {} and k not in kind_licit:
                continue

            new_dict[k] = pruned_v
        return new_dict

    elif isinstance(data, list):
        # Recursively prune items in list, but keep the list itself even if empty
        # (Schemes often distinguish between a missing key and an empty array)
        return [prune_config_dict(i, kind) for i in data]

    return data


def clear_all_editor_widget_keys() -> None:
    """
    Clear all Streamlit widget keys that start with the editor prefix.
    This is used to prevent stale keys from interfering when switching files.
    """
    keys_to_clear = [
        key for key in st.session_state.keys() if key.startswith(EDITOR_WIDGET_PREFIX)
    ]

    if "file_name" in st.session_state:
        keys_to_clear.append("file_name")

    logger.debug(
        f"Clearing {len(keys_to_clear)} editor widget keys from Streamlit state: {keys_to_clear}"
    )

    for key in keys_to_clear:
        del st.session_state[key]
