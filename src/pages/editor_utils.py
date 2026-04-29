from __future__ import annotations

import yaml
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any
from loguru import logger

import streamlit as st
from camel_converter import to_snake

from src.config_utils.schema_validation import ConfigKindType

if TYPE_CHECKING:
    from src.config_utils.config_walker import ConfigWalker
    from src.grammar.registry.feature_marker_registry import Marker

EDITOR_WIDGET_PREFIX = "editor-widget-"

# Marker Editor Constants
_MARKER_TYPE_PREFIX = "marker-type-"
_MARKER_VALUE_PREFIX = "marker-val-"
_MARKER_REPLACE_IN_PREFIX = "marker-replace-in-"
_MARKER_REPLACE_OUT_PREFIX = "marker-replace-out-"
_MARKER_ORDER_PREFIX = "marker-order-"
_REMOVE_MARKER_PREFIX = "remove-marker-"

MARKER_WIDGET_PREFIXES = [
    _MARKER_TYPE_PREFIX,
    _MARKER_VALUE_PREFIX,
    _MARKER_REPLACE_IN_PREFIX,
    _MARKER_REPLACE_OUT_PREFIX,
    _MARKER_ORDER_PREFIX,
    _REMOVE_MARKER_PREFIX,
]

MARKER_TYPES = ["suffix", "prefix", "replace", "rule", "suppletion", "principal_part"]


class EditorBase(ABC):
    """
    Abstract base class for YAML config editors.

    Subclasses implement the four abstract methods to handle the
    editor-specific data model.  The base provides concrete load/save
    orchestration that delegates to those methods.

    Instances are stored directly in st.session_state["editor"].
    """

    def __init__(self, kind: ConfigKindType, config_key: str) -> None:
        """
        Args:
            kind:       The config kind string, e.g. "Inventory".
            config_key: The key used in ConfigWalker.config_data,
                        e.g. "inventory_configs".
        """
        self.kind = kind
        self.config_key = config_key
        self.path: str = ""
        self.config_dir: str = ""
        self.data: dict = {}

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

    # ------------------------------------------------------------------
    # Abstract interface — subclasses must implement
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Concrete lifecycle helpers
    # ------------------------------------------------------------------

    def load_file(self, filepath: str, config_walker: "ConfigWalker") -> None:
        """Clear widget state, then load and parse the given file."""

        logger.info(f"Loading {self.kind} file: {filepath}")

        self.config_dir = str(config_walker.config_dir)
        config_object = config_walker.config_data[self.config_key][filepath]
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


def render_editor_toolbar(
    editor: EditorBase, 
    add_label: str = "Add entry", 
    add_callback: callable = None
) -> None:
    """Generic toolbar for Save, Preview, and Add actions."""
    col_add, col_save, col_preview_toggle, _ = st.columns([1.4, 1.2, 1.6, 5])

    with col_add:
        if add_callback and st.button(f"➕ {add_label}", use_container_width=True):
            add_callback()
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
        show_preview = st.toggle("Show YAML preview", value=False, key=f"preview-toggle-{editor.scope}")

    if show_preview:
        with st.container(border=True):
            st.caption("YAML preview — reflects unsaved edits")
            st.code(yaml.dump(editor.to_yaml(), allow_unicode=True, sort_keys=False))


def prune_config_dict(data: Any, kind: str) -> Any:
    """
    Recursively remove None values and empty strings from a dictionary,
    unless they are explicitly allowed ("licit nulls") by the schema.
    """
    # Define keys that are allowed to be null for specific kinds
    # Format: {Kind: {ParentKey: {LicitNullKey}}} or just {Kind: {LicitNullKey}}
    # We use a set of strings for simple path-based matching
    LICIT_PATHS = {
        "FeatureMarkers": {"markers"}, # markers is a dict, values can be null
        "Paradigm": {"feature_markers"}, # feature_markers is a dict, values can be null
        "Rules": {"input_pattern", "output_pattern"},
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


def editor_guard(kind: ConfigKindType) -> EditorBase:
    """
    Check if an Editor instance is in session state;
    if not, show a prompt and stop execution.
    """

    # check if user just switched from a different page
    current_page = st.session_state.get("current_page", "unknown")
    if current_page != kind:
        st.session_state.pop("editor", None)
        st.session_state["current_page"] = kind

    if "pending_load" in st.session_state:
        logger.info(
            f"Pending load detected in session state: {st.session_state['pending_load']}"
        )
        pending = st.session_state.pop("pending_load")
        editor_class = pending["class"]
        file_name = pending["file_name"]

        editor = editor_class()
        if file_name:
            config_walker = st.session_state.get("config_walker")
            if config_walker is None:
                st.error("Config walker not found in session state.")
                st.stop()
            editor.load_file(file_name, config_walker=config_walker)
        else:
            editor.new_file()

        st.session_state["editor"] = editor
        st.session_state["file_name"] = editor.stem
        st.rerun()

    else:
        editor = st.session_state.get("editor")

    if editor is None:
        st.info(
            "👈 Select a file in the sidebar and click **Open**, or open a **(new file)** to begin."
        )
        st.stop()
    return editor


def editor_sidebar(
    kind: str,
    editor_class: type[EditorBase],
    config_dir: str,
    config_walker: ConfigWalker,
    kind_files: list[str],
    help_str: str,
) -> None:
    """
    Render sidebar for the inventory page, including file selector and about info.
    """
    with st.sidebar:
        st.title(f"🔤 {kind} Editor")
        st.caption(f"`CONFIG_DIR`: `{config_dir}`")
        st.divider()

        st.subheader("Open file")
        file_options = [None] + kind_files
        file_indices = list(range(len(file_options)))

        kind_stems = [Path(f).stem for f in kind_files]
        file_display_options = ["(new file)"] + kind_stems

        if not kind_files:
            st.info(f"No {kind} files found.")

        selected_file_idx = st.selectbox(
            f"{kind} files",
            options=file_indices,
            format_func=lambda i: file_display_options[i],
            key="file_selector",
            label_visibility="collapsed",
        )
        selected_file = file_options[selected_file_idx]

        col_open, col_refresh = st.columns(2)
        with col_open:
            if st.button("Open", use_container_width=True, type="primary"):
                # prepare state handover
                logger.info(
                    f"Open button clicked for file: {selected_file}, editor class: {editor_class} "
                    "setting pending_load in session state and clearing existing editor state."
                )
                clear_all_editor_widget_keys()
                st.session_state["pending_load"] = {
                    "file_name": selected_file,
                    "class": editor_class,
                }
                # clear any existing editor instance
                st.session_state.pop("editor", None)
                st.rerun()

        with col_refresh:
            if st.button(
                "↺ Refresh",
                use_container_width=True,
                help=f"Re-scan CONFIG_DIR for {kind} files",
            ):
                st.rerun()

        st.divider()
        st.subheader("About")
        st.markdown(help_str)


def editor_header(kind: ConfigKindType, editor: type[EditorBase]) -> None:
    """
    Render the page header, including the file name input field.
    The file name is stored in session state and used when saving the YAML file.
    """
    logger.debug(
        f"Rendering header for {kind} editor with file: {editor.path}, stem {editor.stem}"
    )

    st.header(editor.stem or f"New {kind} file")

    col_name, _ = st.columns([3, 5])
    with col_name:
        st.text_input(
            "File name",
            key="file_name",
            placeholder="segments",
            help=f"Name for this {kind} file (no extension needed).",
        )


def render_marker_row(
    marker: "Marker",
    scope: str,
    editor: EditorBase,
    available_rules: list[str],
    available_principal_parts: list[str],
) -> None:
    """Reusable component for rendering a single Marker row."""
    m_uid = marker.uuid
    with st.container(border=True):
        col_type, col_order, col_del = st.columns([1.5, 1.5, 0.4])
        with col_type:
            selected_type = st.selectbox(
                "Type",
                options=MARKER_TYPES,
                index=MARKER_TYPES.index(marker.type)
                if marker.type in MARKER_TYPES
                else 0,
                key=editor.get_widget_key(_MARKER_TYPE_PREFIX, scope, suffix=m_uid),
                label_visibility="collapsed",
            )
            if selected_type != marker.type:
                # Reset value fields when type changes to avoid confusion
                st.rerun()
        with col_order:
            st.text_input(
                "Order",
                value=marker.order or "",
                placeholder="Order stage",
                key=editor.get_widget_key(_MARKER_ORDER_PREFIX, scope, suffix=m_uid),
                label_visibility="collapsed",
            )
        with col_del:
            if st.button(
                "✕",
                key=editor.get_widget_key(_REMOVE_MARKER_PREFIX, scope, suffix=m_uid),
                help="Remove marker",
            ):
                st.session_state[f"pending_remove_marker_{scope}"] = m_uid
                st.rerun()

        if marker.type == "replace":
            r_col1, r_col2 = st.columns(2)
            val_in = marker.value[0] if isinstance(marker.value, tuple) else ""
            val_out = marker.value[1] if isinstance(marker.value, tuple) else ""
            with r_col1:
                st.text_input(
                    "Input",
                    value=val_in,
                    key=editor.get_widget_key(
                        _MARKER_REPLACE_IN_PREFIX, scope, suffix=m_uid
                    ),
                )
            with r_col2:
                st.text_input(
                    "Output",
                    value=val_out,
                    key=editor.get_widget_key(
                        _MARKER_REPLACE_OUT_PREFIX, scope, suffix=m_uid
                    ),
                )
        elif marker.type == "rule":
            st.selectbox(
                "Rule",
                options=[""] + available_rules,
                index=available_rules.index(marker.value.lstrip("$")) + 1
                if isinstance(marker.value, str) and marker.value.lstrip("$") in available_rules
                else 0,
                key=editor.get_widget_key(_MARKER_VALUE_PREFIX, scope, suffix=m_uid),
            )
        elif marker.type == "principal_part":
            st.selectbox(
                "Principal Part",
                options=[""] + available_principal_parts,
                index=available_principal_parts.index(marker.value) + 1
                if isinstance(marker.value, str) and marker.value in available_principal_parts
                else 0,
                key=editor.get_widget_key(_MARKER_VALUE_PREFIX, scope, suffix=m_uid),
            )
        else:
            st.text_input(
                "Value",
                value=marker.value if isinstance(marker.value, str) else "",
                key=editor.get_widget_key(_MARKER_VALUE_PREFIX, scope, suffix=m_uid),
                placeholder="e.g. -o, ba-",
            )


def render_marker_list(
    markers: list["Marker"],
    scope: str,
    editor: EditorBase,
    available_rules: list[str],
    available_principal_parts: list[str],
    label: str = "Markers",
) -> None:
    """Reusable component for rendering a list of Markers."""
    st.subheader(label)

    # Check for pending removals
    pending_rm = st.session_state.pop(f"pending_remove_marker_{scope}", None)
    if pending_rm:
        # Subclasses must implement remove_marker(markers, m_uuid)
        if hasattr(editor, "remove_marker"):
            editor.remove_marker(markers, pending_rm)
        st.rerun()

    if not markers:
        st.info("Zero marking (no markers).")
    else:
        for m in markers:
            render_marker_row(
                m, scope, editor, available_rules, available_principal_parts
            )

    if st.button(f"➕ Add marker to {label.lower()}", key=f"add-m-{scope}"):
        if hasattr(editor, "add_marker"):
            editor.add_marker(markers)
        st.rerun()
