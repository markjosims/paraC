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
from pathlib import Path

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

_NODE_PREFIXES = ("name-", "ref-", "items_kind-", "items_text-")

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
    parent_id: str = "item",
) -> tuple[dict[str, InventoryClass], dict[str, list[str]]]:
    """
    Build item_map and node_id_map from a list of top-level nodes
    using depth-first traversal.
    """
    item_map: dict[str, InventoryClass] = {}
    node_id_map: dict[str, list[str]] = {}

    def _traverse(nodes: list[InventoryClass], sub_parent_id: str) -> None:
        node_id_map[sub_parent_id] = []
        for i, node in enumerate(nodes):
            node_id = f"{sub_parent_id}-{i}"
            item_map[node_id] = node
            node_id_map[sub_parent_id].append(node_id)
            if node.type == "nested_class":
                _traverse(node.children, sub_parent_id=node_id)

    _traverse(top_items, sub_parent_id=parent_id)
    return item_map, node_id_map


def _validate_node_id(node_id: str) -> list[int]:
    """
    Verify node id has format "item-INT[-INT...]" and return the list
    of integer indices.
    """
    if not node_id.startswith("item-"):
        raise ValueError(
            f"Expected node id with format `item-$INT-$INT-...` but got {node_id}"
        )
    index_strs = node_id.removeprefix("item-").split("-")
    try:
        return [int(s) for s in index_strs]
    except ValueError:
        raise ValueError(
            "Error parsing node id indices — expected integers after `item-` prefix. "
            f"Got: {index_strs}"
        )


"""
InventoryEditor
"""


class InventoryEditor(EditorBase):
    """
    Editor for Inventory YAML configs.

    self.data keys:
        top_items   — list[InventoryClass], the root nodes of the tree
        item_map    — dict[node_id, InventoryClass]
        node_id_map — dict[parent_node_id, list[child_node_id]]
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
        item_map, node_id_map = _populate_node_map(top_items)
        return {
            "top_items": top_items,
            "item_map": item_map,
            "node_id_map": node_id_map,
        }

    def read_form_to_state(self) -> None:
        """
        Sync widget values from st.session_state back into InventoryClass
        objects.  Rebuilds children lists for leaf nodes from the
        comma-separated items text field.
        """
        item_map: dict[str, InventoryClass] = self.data.get("item_map", {})
        for node_id, node in item_map.items():
            name_val = st.session_state.get(f"name-{node_id}")
            ref_val = st.session_state.get(f"ref-{node_id}")
            if name_val is not None:
                node.name = name_val
            if ref_val is not None:
                node.value = ref_val

            if node.type != "nested_class":
                kind_val = st.session_state.get(f"items_kind-{node_id}")
                items_val = st.session_state.get(f"items_text-{node_id}")
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

    def clear_widget_keys(self) -> None:
        """
        Remove all widget keys for the current inventory from
        st.session_state.  Does NOT modify self.data — item_map is
        rebuilt on next load.
        """
        item_map: dict[str, InventoryClass] = self.data.get("item_map", {})
        for node_id in list(item_map.keys()):
            for prefix in _NODE_PREFIXES:
                st.session_state.pop(f"{prefix}{node_id}", None)
            for i in range(len(DIAC_TOKENS)):
                st.session_state.pop(f"diac-{node_id}-{i}", None)

    """
    Tree accessors
    """

    def get_node(self, node_id: str) -> InventoryClass | None:
        return self.data["item_map"].get(node_id)

    def get_child_ids(self, node_id: str) -> list[str] | None:
        return self.data["node_id_map"].get(node_id)

    def get_parent_id(self, node_id: str) -> str | None:
        indices = _validate_node_id(node_id)
        if len(indices) == 1:
            return None
        return "item-" + "-".join(str(i) for i in indices[:-1])

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
        new_id = f"item-{len(top_items) - 1}"
        item_map[new_id] = new_node
        self.data["node_id_map"]["item"].append(new_id)
        return new_id

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
        new_id = f"{parent_id}-{len(parent_node.children) - 1}"
        self.data["item_map"][new_id] = new_child
        self.data["node_id_map"].setdefault(parent_id, []).append(new_id)
        return new_id

    def pop_node(self, node_id: str) -> InventoryClass:
        """
        Remove a node from the tree, clear its widget keys, and
        reindex any following siblings whose node_ids would shift.
        Returns the removed node.
        """
        indices = _validate_node_id(node_id)
        item_map: dict = self.data["item_map"]
        top_items: list[InventoryClass] = self.data["top_items"]
        node_id_map: dict = self.data["node_id_map"]

        # Clear widget keys for this node and its subtree before mutating
        self._clear_subtree_keys(node_id)

        if len(indices) == 1:
            # Top-level node
            popped = top_items.pop(indices[0])
            # Rebuild entire top-level index since following siblings shift
            updated_item_map, updated_node_id_map = _populate_node_map(top_items)
            self.data["item_map"] = updated_item_map
            self.data["node_id_map"] = updated_node_id_map
            return popped

        # Nested node
        parent_id = self.get_parent_id(node_id)
        parent_node = item_map[parent_id]
        sibling_ids = node_id_map.get(parent_id, [])
        is_last = sibling_ids[-1] == node_id if sibling_ids else True

        popped = parent_node.children.pop(indices[-1])

        if is_last:
            # No following siblings — just remove from maps
            item_map.pop(node_id, None)
            node_id_map.pop(node_id, None)
            if node_id in sibling_ids:
                sibling_ids.remove(node_id)
        else:
            # Clear widget keys for following siblings (their ids will change)
            following = sibling_ids[indices[-1] + 1 :]
            for sid in following:
                self._clear_subtree_keys(sid)
            # Rebuild the subtree under parent
            updated_item_map, updated_node_id_map = _populate_node_map(
                parent_node.children, parent_id
            )
            item_map.update(updated_item_map)
            node_id_map.update(updated_node_id_map)

        return popped

    def _clear_subtree_keys(self, node_id: str) -> None:
        """
        Remove widget keys for node_id and all descendants from
        st.session_state, then remove them from item_map/node_id_map.
        """
        item_map: dict = self.data["item_map"]
        node = item_map.pop(node_id, None)
        if node is None:
            return
        for prefix in _NODE_PREFIXES:
            st.session_state.pop(f"{prefix}{node_id}", None)
        for i in range(len(DIAC_TOKENS)):
            st.session_state.pop(f"diac-{node_id}-{i}", None)
        if node.type == "nested_class":
            child_ids = self.data["node_id_map"].pop(node_id, [])
            for child_id in child_ids:
                self._clear_subtree_keys(child_id)


"""
Node rendering (recursive)
"""


def _render_node(node_id: str, editor: InventoryEditor, depth: int = 0) -> None:
    """Render a single inventory node and recurse into children."""
    # TODO: currently no way to edit the type of a nested_class node or convert
    # between phone_class and flag_class — add this in the future if needed
    node = editor.get_node(node_id)
    assert node is not None, f"Cannot render non-existent node: {node_id}"
    is_nested = node.type == "nested_class"

    if depth > 0:
        indent_ratio = min(depth * 0.035, 0.25)
        _, content_col = st.columns([indent_ratio, 1.0 - indent_ratio])
    else:
        content_col = st

    node_ref = node.value or "(ref not set)"
    with content_col.popover(f"{node.name} `{node_ref}`"):
        col_name, col_ref = st.columns(2)
        with col_name:
            st.text_input(
                "Node name",
                key=f"name-{node_id}",
                value=node.name,
                placeholder="consonants",
            )
        with col_ref:
            st.text_input(
                "Reference",
                key=f"ref-{node_id}",
                value=node_ref,
                placeholder="<C>",
            )

        if is_nested:
            st.text_input(
                "Node contents",
                value="Child nodes",
                disabled=True,
                key=f"_disabled-{node_id}",
            )
            st.caption("This node has children — phones and flags are disabled.")
        else:
            col_kind, col_items = st.columns(2)
            with col_kind:
                kind_options = ["phones", "flags"]
                selected_index = kind_options.index(
                    "flags" if node.type == "flag_class" else "phones"
                )
                st.selectbox(
                    "Item type",
                    options=kind_options,
                    index=selected_index,
                    key=f"items_kind-{node_id}",
                )
            with col_items:
                st.text_input(
                    "Items",
                    key=f"items_text-{node_id}",
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
            if st.button("＋ Add child", key=f"add-child-{node_id}"):
                editor.insert_child(node_id)
                st.rerun()
        with btn_remove:
            if st.button("✕ Delete item", key=f"remove-{node_id}"):
                editor.pop_node(node_id)
                st.rerun()

    if is_nested:
        for child_id in editor.get_child_ids(node_id):
            _render_node(child_id, editor, depth + 1)


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
        editor.read_form_to_state()
        with st.container(border=True):
            st.caption("YAML preview — reflects unsaved edits")
            import yaml as _yaml

            st.code(_yaml.dump(editor.to_yaml(), allow_unicode=True, sort_keys=False))


def node_tree(editor: InventoryEditor) -> None:
    """
    Render the tree of inventory nodes by recursively rendering from the top-level nodes.
    """
    top_node_ids = editor.data.get("node_id_map", {}).get("item", [])

    if not top_node_ids:
        st.info(
            "No nodes yet. Click **➕ Add top-level node** to start — "
            "for example a `consonants` or `vowels` category."
        )
    else:
        for node_id in top_node_ids:
            _render_node(node_id, editor, depth=0)


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

    editor_header(kind=_config_kind, editor=editor)
    inventory_toolbar(editor)

    st.divider()

    node_tree(editor)


if __name__ == "__main__":
    inventory_page()
