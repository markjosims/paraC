"""
Streamlit Inventory Editor
==========================
A UI for creating and editing phoneme/symbol inventory YAML configs.

Requires:
    CONFIG_DIR  — environment variable pointing to the config root directory.
                  All YAML files with kind: Inventory are auto-discovered from
                  that directory (recursive glob).

Usage:
    CONFIG_DIR=/path/to/configs streamlit run src/streamlit/app.py

BUG: state does not get torn down when switching from one inventory page to another
resulting in merged data
"""

from __future__ import annotations
import yaml
from typing import Literal

import streamlit as st
from src.grammar.registry.inventory_registry import (
    InventoryClass,
    InventoryItem,
    InventoryRegistry,
)
from src.config_utils.config_walker import ConfigWalker
from src.pages.editor_utils import (
    EditorBase,
    editor_guard,
    editor_sidebar,
    editor_header,
)
from loguru import logger

"""
Constants
"""

DIAC_TOKENS: list[str] = [
    "<DIAC:á>",
    "<DIAC:à>",
    "<DIAC:ā>",
    "<DIAC:ǎ>",
    "<DIAC:â>",
    "<DIAC:ã>",
]

_NODE_NAME_PREFIX = "name-"
_NODE_REF_PREFIX = "ref-"
_NODE_KIND_PREFIX = "items_kind-"
_NODE_ITEMS_PREFIX = "items_text-"
_ADD_CHILD_PREFIX = "add-child-"
_REMOVE_PREFIX = "remove-"
_DISABLED_PREFIX = "_disabled-"
_CHANGE_TYPE_PREFIX = "change-type-"
_WIDGET_PREFIXES: list[str] = [
    _NODE_NAME_PREFIX,
    _NODE_REF_PREFIX,
    _NODE_KIND_PREFIX,
    _NODE_ITEMS_PREFIX,
    _ADD_CHILD_PREFIX,
    _REMOVE_PREFIX,
    _DISABLED_PREFIX,
    _CHANGE_TYPE_PREFIX,
]

_config_kind = "Inventory"
_config_key = "inventory_configs"

_help_str = """
    Inventory files define phoneme and symbol sets used by the FST parser.
    Each node can contain **phones** (consonants, vowels, tones) or **flags**
    (internal markers). See `README.md` for the full schema.
"""


"""
Static helpers — no dependency on editor state
"""


def _populate_node_map(
    top_items: list[InventoryClass],
) -> dict[str, InventoryClass]:
    """
    Build item_map from a list of top-level nodes
    using depth-first traversal.
    """
    item_map: dict[str, InventoryClass] = {}

    def _traverse(nodes: list[InventoryClass]) -> None:
        for node in nodes:
            item_map[node.uuid] = node
            if node.type == "nested_class":
                _traverse(node.children)

    _traverse(top_items)
    return item_map


"""
InventoryEditor
"""


class InventoryEditor(EditorBase):
    """
    Editor for Inventory YAML configs.

    self.data keys:
        top_items   — list[InventoryClass], the root nodes of the tree
        item_map    — dict[node_id, InventoryClass]
    """

    def __init__(self) -> None:
        super().__init__(kind=_config_kind, config_key=_config_key)

    """
    EditorBase abstract methods
    """

    def build_state_from_config(self, config_object: dict) -> dict:
        filepath = config_object["source_path"]
        inventory_reg = InventoryRegistry(config_objects={filepath: config_object})
        top_items = inventory_reg.top_items
        item_map = _populate_node_map(top_items)
        return {
            "top_items": top_items,
            "item_map": item_map,
        }

    def read_form_to_state(self) -> None:
        """
        Sync widget values from st.session_state back into InventoryClass
        objects.  Rebuilds children lists for leaf nodes from the
        comma-separated items text field.
        """

        item_map: dict[str, InventoryClass] = self.data.get("item_map", {})
        for node_id, node in item_map.items():
            name_val = self.get_node_widget(_NODE_NAME_PREFIX, node_id)
            ref_val = self.get_node_widget(_NODE_REF_PREFIX, node_id)
            if name_val is not None:
                node.name = name_val
            if ref_val is not None:
                node.value = ref_val

            kind_val = self.get_node_widget(_NODE_KIND_PREFIX, node_id)
            if kind_val and kind_val != node.type:
                self.change_node_type(node_id, new_type=kind_val)

            if kind_val != "nested_class":
                items_val = self.get_node_widget(_NODE_ITEMS_PREFIX, node_id)
                if kind_val is not None:
                    node.type = "phone_class" if kind_val == "phones" else "flag_class"
                if items_val is not None:
                    item_type = "phone" if node.type == "phone_class" else "flag"
                    raw_items = [s.strip() for s in items_val.split(",") if s.strip()]
                    node.children = [
                        InventoryItem(value=v, parent=node, type=item_type)
                        for v in raw_items
                    ]

    def to_yaml(self) -> dict:
        top_items: list[InventoryClass] = self.data.get("top_items", [])
        return {
            "kind": self.kind,
            "data": [node.to_dict() for node in top_items],
        }

    def get_default_data(self) -> dict:
        return {
            "top_items": [],
            "item_map": {},
        }

    """
    Tree accessors
    """

    def get_node(self, node_id: str) -> InventoryClass | None:
        return self.data["item_map"].get(node_id)

    def get_parent_id(self, node_id: str) -> str | None:
        node = self.get_node(node_id)
        if node and node.parent:
            parent_node = node.parent
            return parent_node.uuid
        return None

    """
    Tree mutations
    """

    def insert_top_node(self) -> str:
        """Append a new top-level node; return its node_id."""
        new_node = InventoryClass(
            name="new_node",
            value="<new_node_ref>",
            type="phone_class",
            children=[],
        )
        top_items: list[InventoryClass] = self.data["top_items"]
        item_map: dict = self.data["item_map"]
        top_items.append(new_node)
        item_map[new_node.uuid] = new_node
        return new_node.uuid

    def insert_child(self, parent_id: str) -> str:
        """Append a new child under parent_id; return the child's node_id."""
        parent_node = self.get_node(parent_id)
        if parent_node is None or parent_node.type != "nested_class":
            raise ValueError(
                f"Cannot add child to {parent_id!r}: node does not exist or is not a nested_class."
            )
        new_child = InventoryClass(
            name="new_node",
            value="<new_node_ref>",
            type="phone_class",
            children=[],
        )
        parent_node.children.append(new_child)
        self.data["item_map"][new_child.uuid] = new_child
        return new_child.uuid

    def pop_node(self, node_id: str) -> InventoryClass:
        """
        Remove a node from the tree, clear its widget keys, and
        reindex any following siblings whose node_ids would shift.
        Returns the removed node.
        """
        item_map: dict = self.data["item_map"]
        top_items: list[InventoryClass] = self.data["top_items"]

        if node_id not in item_map:
            return None

        # Clear widget keys for this node and its subtree before mutating
        self._clear_subtree_keys(node_id)

        popped_node: InventoryClass = item_map.pop(node_id)

        parent = popped_node.parent
        if parent is None:
            # Top-level node
            top_items.remove(popped_node)
        else:
            parent.children.remove(popped_node)

        if popped_node.type == "nested_class":
            # remove children
            for child in popped_node.children:
                child_id = child.uuid
                self.pop_node(child_id)

        return popped_node

    def change_node_type(
        self,
        node_id: str,
        new_type: Literal["phone_class", "flag_class", "nested_class"],
    ) -> None:
        """
        Change the type of a node, clearing children if switching to a leaf type.
        """
        logger.debug(f"Changing node {node_id} to type {new_type}")

        node = self.get_node(node_id)
        if node is None:
            raise ValueError(f"Node {node_id!r} does not exist.")

        if node.type == new_type:
            return  # no change

        if node.type == "nested_class":
            # Switching from nested_class, remove child nodes
            for child in node.children:
                child_id = child.uuid
                self.pop_node(child_id)

        node.type = new_type
        node.children = []

    def _clear_subtree_keys(self, node_id: str) -> None:
        """Recursively clear widget keys for a node and its descendants."""
        item_map: dict[str, InventoryClass] = self.data["item_map"]

        # Clear keys for this node
        for prefix in _WIDGET_PREFIXES:
            st.session_state.pop(f"{prefix}{node_id}", None)

        # Recurse into children if nested_class
        node = item_map.get(node_id)
        if node and node.type == "nested_class":
            for child in node.children:
                child: InventoryClass
                self._clear_subtree_keys(child.uuid)


"""
Node rendering (recursive)
"""


def _render_node(node: InventoryClass, editor: InventoryEditor, depth: int = 0) -> None:
    """Render a single inventory node and recurse into children."""

    is_nested = node.type == "nested_class"

    if depth > 0:
        indent_ratio = min(depth * 0.035, 0.25)
        _, content_col = st.columns([indent_ratio, 1.0 - indent_ratio])
    else:
        content_col = st

    node_ref = node.value or "(ref not set)"
    node_caption = f"{node.name} `{node_ref}`"

    if not is_nested:
        item_str = ", ".join(child.value for child in node.children)
        node_caption += f": `{item_str}`"

    with content_col.popover(node_caption):
        col_name, col_ref = st.columns(2)
        with col_name:
            st.text_input(
                "Node name",
                key=editor.get_widget_key(_NODE_NAME_PREFIX, node.uuid),
                value=node.name,
                placeholder="consonants",
            )
        with col_ref:
            st.text_input(
                "Reference",
                key=editor.get_widget_key(_NODE_REF_PREFIX, node.uuid),
                value=node_ref,
                placeholder="<C>",
            )

        class_names = ["phone_class", "flag_class", "nested_class"]
        selected_index = class_names.index(node.type) if node.type in class_names else 0
        new_type = st.selectbox(
            "Item type",
            options=class_names,
            index=selected_index,
            format_func=lambda s: s.replace("_class", "").capitalize(),
            key=editor.get_widget_key(_NODE_KIND_PREFIX, node.uuid),
        )

        st.button(
            "Change node type",
            disabled=(new_type == node.type),
            key=editor.get_widget_key(_CHANGE_TYPE_PREFIX, node.uuid),
            on_click=editor.change_node_type,
            args=(node.uuid, new_type),
        )


        if is_nested:
            st.text_input(
                "Node contents",
                value="Child nodes",
                disabled=True,
                key=editor.get_widget_key(_DISABLED_PREFIX, node.uuid),
            )
            st.caption("This node has children — phones and flags are disabled.")
        else:
            st.text_input(
                "Items",
                key=editor.get_widget_key(_NODE_ITEMS_PREFIX, node.uuid),
                value=", ".join(node.item_strs()),
                placeholder="p, t, k",
            )

            with st.expander("🔡 Insert diacritic"):
                st.caption(
                    "Click a diacritic token to append it to the Items field. "
                    "Tokens are resolved to combining characters on save."
                )
                diac_cols = st.columns(len(DIAC_TOKENS))
                for i, token in enumerate(DIAC_TOKENS):
                    diac_cols[i].code(token, language="text")

        btn_add, btn_remove = st.columns(2)
        with btn_add:
            if st.button(
                "＋ Add child",
                key=editor.get_widget_key(_ADD_CHILD_PREFIX, node.uuid),
                disabled=not is_nested,
            ):
                editor.insert_child(node.uuid)
                st.rerun()
        with btn_remove:
            if st.button(
                "✕ Delete item", key=editor.get_widget_key(_REMOVE_PREFIX, node.uuid)
            ):
                editor.pop_node(node.uuid)
                st.rerun()

    if is_nested:
        for child in node.children:
            _render_node(child, editor, depth + 1)


"""
Page components
"""


def inventory_toolbar(editor: InventoryEditor) -> None:
    """
    Render toolbar with buttons for adding nodes, saving YAML, and toggling the preview pane.
    """
    col_add, col_save, col_preview_toggle, _ = st.columns([1.4, 1.2, 1.6, 5])

    with col_add:
        if st.button("➕ Add top-level node", use_container_width=True):
            editor.insert_top_node()
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

    # YAML preview
    if show_preview:
        with st.container(border=True):
            st.caption("YAML preview — reflects unsaved edits")

            st.code(yaml.dump(editor.to_yaml(), allow_unicode=True, sort_keys=False))


def node_tree(editor: InventoryEditor) -> None:
    """
    Render the tree of inventory nodes by recursively rendering from the top-level nodes.
    """
    top_nodes = editor.data["top_items"]

    if not top_nodes:
        st.info(
            "No nodes yet. Click **➕ Add top-level node** to start — "
            "for example a `consonants` or `vowels` category."
        )
    else:
        for node in top_nodes:
            _render_node(node, editor, depth=0)


"""
Page function
"""


def inventory_page() -> None:
    st.set_page_config(
        page_title="Inventory Editor",
        page_icon="🔤",
        layout="wide",
    )

    config_dir: str = st.session_state["config_dir"]
    config_walker: ConfigWalker = st.session_state["config_walker"]
    inventory_files = config_walker.config_filemap[_config_key]

    editor_sidebar(
        _config_kind,
        InventoryEditor,
        config_dir,
        config_walker,
        inventory_files,
        _help_str,
    )
    editor = editor_guard(kind=_config_kind)
    editor.read_form_to_state()
    editor_header(kind=_config_kind, editor=editor)
    toolbar_placeholder = st.empty()

    st.divider()

    node_tree(editor)

    # render after node tree so that buttons are within the context of the editor content
    with toolbar_placeholder.container():
        inventory_toolbar(editor)


if __name__ == "__main__":
    inventory_page()
