"""
Streamlit Inventory Editor
==========================
A UI for creating and editing phoneme/symbol inventory YAML configs.

Requires:
    CONFIG_DIR  — environment variable pointing to the config root directory.
                  All YAML files with kind: Inventory are auto-discovered from
                  that directory (recursive glob).

Usage:
    CONFIG_DIR=/path/to/configs streamlit run inventory_editor_app.py
"""

from __future__ import annotations
import os

import streamlit as st
from src.grammar.registry.inventory_registry import (
    InventoryClass,
    InventoryRegistry,
)
from src.config_utils.config_walker import ConfigWalker
from src.pages.editor_utils import EditorState

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DIAC_TOKENS: list[str] = [
    "<DIAC:á>",
    "<DIAC:à>",
    "<DIAC:ā>",
    "<DIAC:ǎ>",
    "<DIAC:â>",
    "<DIAC:ã>",
]

# Only InventoryClass is to be rendered: phone/flag leaf nodes
# are built from CSVs in form for InventoryClass
# and stored internally

_config_kind = "Inventory"
_config_key = "inventory_configs"

"""
File loading and state initialization logic.
Statefulness lifecycle:
- Fetch YAML data from ConfigWalker
- Load Inventory tree using InventoryRegistry
- Map Inventory classes to unique ids reflecting position in tree
- Store in session state:
    - top_items: list of top-level InventoryClass nodes (for rendering and YAML output)
    - item_map: node_id -> InventoryClass
    - node_id_map: parent_node_id -> list of child node_ids
"""


def _load_file(filepath: str) -> None:
    """Load an inventory file into session state, clearing stale widget keys."""
    editor_state: EditorState | None = st.session_state.get("editor_state", None)
    if editor_state is not None:
        node_keys = editor_state.data["item_map"].keys()
        node_keys = list(node_keys)
        _clear_node_state_keys(node_ids=node_keys)
    config_walker: ConfigWalker = st.session_state["config_walker"]
    try:
        config_object = config_walker.config_data[_config_key][filepath]
        inventory_reg = InventoryRegistry(config_objects={filepath: config_object})
        top_items = inventory_reg.top_items
        item_map, node_id_map = _populate_node_map(top_items)
        state = EditorState(
            path=filepath,
            kind=_config_kind,
            data={
                "item_map": item_map,
                "top_items": top_items,
                "node_id_map": node_id_map,
            },
        )
    except KeyError:
        st.error(f"File not found: `{filepath}`")
        return
    except ValueError as exc:
        st.error(str(exc))
        return
    st.session_state.editor_state = state
    st.session_state.loaded_file = filepath


def _new_file() -> None:
    """Reset editor to a blank state."""
    editor_state = st.session_state.get("editor_state", None)
    if editor_state is not None:
        node_id_map = editor_state.data["node_id_map"]
        top_ids = node_id_map["item"]
        _clear_node_state_keys(top_ids)
    st.session_state.editor_state = EditorState(path="", kind=_config_kind)
    st.session_state.loaded_file = None
    # also reset the path widget
    st.session_state.pop("path", None)


def _populate_node_map(
    top_items: list[InventoryClass],
    parent_id: str = "item",
) -> tuple[dict[str, InventoryClass], dict[str, list[str]]]:
    """
    Helper function to populate item_map and node_id_map from list of top nodes
    using depth-first downward traversal.
    """
    item_map = {}
    node_id_map = {}

    def _traverse_nodes(
        nodes: list[InventoryClass], sub_parent_id: str = parent_id
    ) -> None:
        node_id_map[sub_parent_id] = []
        for i, node in enumerate(nodes):
            node_id = f"{sub_parent_id}-{i}"

            item_map[node_id] = node
            node_id_map[sub_parent_id].append(node_id)

            if node.type == "nested_class":
                _traverse_nodes(node.children, sub_parent_id=node_id)

    _traverse_nodes(top_items, sub_parent_id=parent_id)
    return item_map, node_id_map


def _inventory_tree_to_dict(top_items: list[InventoryClass]) -> list[dict]:
    """
    Convert inventory tree to a serializable format for YAML output.
    This is the inverse of loading the tree from YAML.
    """

    return [node.to_dict() for node in top_items]


"""
State mutation logic: insert/remove nodes, update widget keys, sync form to state.
State mutation lifecycle:
- Insert/remove node from tree (e.g. _insert_child, _pop_node)
- Update item_map with new node ids and node objects (_put_node_to_state)
- Clear widget keys for removed nodes and their subtree (_clear_node_widget_keys)
"""


def _pop_node(node_id: str) -> None:
    """
    Remove a node from the tree, clear its widget keys
    and reindex siblings if necessary.
    """
    indices = _validate_node_id(node_id)
    data: dict = st.session_state.editor_state.data
    item_map = data["item_map"]
    top_items = data["top_items"]
    node_id_map = data["node_id_map"]
    top_ids = node_id_map["item"]
    if len(indices) == 1 and indices[0] < len(top_items) - 1:
        # top level node
        # recompute node ids and keys for top-level after pop, since all indices shift
        popped = top_items.pop(indices[0])
        _clear_node_state_keys(top_ids)
        updated_item_map, updated_node_id_map = _populate_node_map(top_items)
        data["item_map"] = updated_item_map
        data["node_id_map"] = updated_node_id_map

        return popped

    if len(indices) == 1:
        # last top-level node, just pop without reindexing since no siblings after it
        popped = top_items.pop(indices[0])
        _clear_node_state_keys([node_id])
        return popped

    # nested node
    parent_id = _get_parent_id(node_id)
    sibling_ids = node_id_map.get(parent_id)
    parent_node = item_map.get(parent_id)

    # check if current node is last sibling
    # if so, clear current node's state keys and pop without reindexing
    # since no siblings after it
    if sibling_ids and sibling_ids[-1] == node_id:
        popped = parent_node.children.pop(indices[-1])
        _clear_node_state_keys([node_id])
        return popped

    # pop node from parent's children
    popped = parent_node.children.pop(indices[-1])
    _clear_node_state_keys([node_id])

    # clear widget keys for all siblings after the popped node
    # since their indices shift
    following_sibling_ids = sibling_ids[indices[-1] + 1 :]
    _clear_node_state_keys(following_sibling_ids)

    # then reindex siblings after popped node and update item_map and node_id_map
    updated_item_map, updated_node_id_map = _populate_node_map(
        parent_node.children, parent_id
    )
    data = st.session_state.editor_state.data
    item_map = data["item_map"]
    node_id_map = data["node_id_map"]
    item_map.update(updated_item_map)
    node_id_map.update(updated_node_id_map)

    return popped


def _insert_top_node() -> str:
    """
    Insert a new top-level node. Returns the ID of the newly inserted node.
    """
    new_node = InventoryClass(
        name="new_node",
        value="<new_node_ref>",
        type="phone_class",
        children=[],
    )
    data: dict = st.session_state.editor_state.data
    top_items = data["top_items"]
    item_map = data["item_map"]
    top_items.append(new_node)
    new_node_id = f"item-{len(top_items) - 1}"
    item_map[new_node_id] = new_node
    return new_node_id


def _insert_child(parent_id: str) -> str:
    """
    Insert a new child node under the specified parent node.
    Returns the ID of the newly inserted child node.
    """
    parent_node = _get_node(parent_id)
    if parent_node.type != "nested_class":
        raise ValueError(
            f"Cannot add child to node {parent_id} because it is not a nested class."
        )
    new_child = InventoryClass(
        name="new_node",
        value=f"<new_node_ref>",
        type="phone_class",
        children=[],
    )
    parent_node.children.append(new_child)
    new_child_id = f"{parent_id}-{len(parent_node.children) - 1}"
    _put_node_to_state(new_child_id, new_child)
    return new_child_id


def _clear_node_state_keys(node_ids: list[str]) -> None:
    """
    Remove all widget keys for a node subtree from session state.
    """
    data = st.session_state.editor_state.data
    item_map = data["item_map"]
    for node_id in node_ids[:]:
        try:
            node = item_map.pop(node_id)
            for prefix in ("name-", "ref-", "items_kind-", "items_text-"):
                st.session_state.pop(f"{prefix}{node_id}", None)
            for i in range(len(DIAC_TOKENS)):
                st.session_state.pop(f"diac-{node_id}-{i}", None)
            if node.type == "nested_class":
                child_ids = _get_child_ids(node_id)
                _clear_node_state_keys(child_ids)
        except KeyError:
            continue


def _put_node_to_state(
    node_id: str, node: InventoryClass, old_id: str | None = None
) -> None:
    """
    Assign node to node_id in editor_state.item_map. Do not update
    any widgets here, as that logic is handled by `_render_node`
    and widget keys are derived from node_id.

    If old_id is provided, removes old_id from item_map.
    This is used when reindexing siblings after a pop operation
    to update node_ids to match new indices.
    """
    item_map = st.session_state.editor_state.data.item_map
    if old_id is not None:
        item_map.pop(old_id, None)
    item_map[node_id] = node


def _get_node(node_id: str) -> InventoryClass | None:
    """Get the InventoryClass node corresponding to the given node_id."""
    data: dict = st.session_state.editor_state.data
    item_map = data["item_map"]
    return item_map.get(node_id, None)

def _get_child_ids(node_id: str) -> list[str] | None:
    data: dict = st.session_state.editor_state.data
    node_id_map = data["node_id_map"]
    child_ids = node_id_map.get(node_id, None)
    return child_ids

def _get_parent_id(node_id: str) -> str | None:
    """Get the node_id of the parent of the given node_id, or None if top-level."""
    indices = _validate_node_id(node_id)
    if len(indices) == 1:
        return None
    parent_indices = indices[:-1]
    parent_id = "item-" + "-".join(str(i) for i in parent_indices)
    return parent_id


def _validate_node_id(node_id: str) -> list[int]:
    """
    Verifies node id conforms to format "item-INT-INT-INT"
    and returns list of integers indicating node index within tree.
    """
    if not node_id.startswith("item-"):
        raise ValueError(
            f"Expected node id with format `item-$INT-$INT-$INT... but got {node_id}"
        )
    index_strs = node_id.removeprefix("item-").split("-")
    try:
        indices = [int(i_str) for i_str in index_strs]
    except ValueError:
        raise ValueError(
            "Error parsing node id indices — expected integers after `item-` prefix. "
            f"Got: {index_strs}"
        )
    return indices


"""
Node rendering (recursive)
"""

def _render_node(node_id: str, depth: int = 0) -> None:
    """Render a single inventory node and recurse into children."""
    
    node = _get_node(node_id)
    assert node is not None, "Error: cannot render non-existent node with id " + node_id
    is_nested = node.type == "nested_class"

    # Visual indentation: pair an invisible spacer column with the content column.
    if depth > 0:
        indent_ratio = min(depth * 0.035, 0.25)
        _, content_col = st.columns([indent_ratio, 1.0 - indent_ratio])
    else:
        content_col = st

    node_ref = node.value or "(ref not set)"
    with content_col.popover(f"{node.name} `{node_ref}`"):
        # ── Name & Reference ──────────────────────────────────────────────
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

        # ── Items (phones / flags) — disabled when node has children ──────
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
                if node.type == "flag_class":
                    selected_index = kind_options.index("flags")
                else:
                    selected_index = kind_options.index("phones")
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

            # Diacritics bar
            with st.expander("🔡 Insert diacritic"):
                st.caption(
                    "Click a diacritic token to append it to the Items field. "
                    "Tokens are resolved to combining characters on save."
                )
                diac_cols = st.columns(len(DIAC_TOKENS))
                for i, token in enumerate(DIAC_TOKENS):
                    diac_cols[i].code(token, language="text")

        # ── Node actions ──────────────────────────────────────────────────
        btn_add, btn_remove = st.columns(2)
        with btn_add:
            if st.button("＋ Add child", key=f"add-child-{node_id}"):
                _insert_child(node_id)
                st.rerun()
        with btn_remove:
            if st.button("✕ Delete item", key=f"remove-{node_id}"):
                _pop_node(node_id)
                st.rerun()

    # Render children below the parent box, each with one additional level of indent.
    if is_nested:
        child_ids = _get_child_ids(node_id)
        for child_id in child_ids:
            _render_node(child_id, depth + 1)


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

    # ── Sidebar: file picker ───────────────────────────────────────────────
    with st.sidebar:
        st.title("🔤 Inventory Editor")
        st.caption(f"`CONFIG_DIR`: `{config_dir}`")
        st.divider()

        st.subheader("Open file")
        file_options = [None] + inventory_files
        file_indices = list(range(len(file_options)))

        inventory_basenames = [os.path.basename(file) for file in inventory_files]
        file_display_options = ["(new file)"] + inventory_basenames

        if not inventory_files:
            st.info(f"No Inventory YAML files found under `{config_dir}`.")

        selected_file_idx = st.selectbox(
            "Inventory files",
            options=file_indices,
            format_func=lambda i: file_display_options[i],
            key="file_selector",
            label_visibility="collapsed",
        )
        selected_file = file_options[selected_file_idx]

        col_open, col_refresh = st.columns(2)
        with col_open:
            if st.button("Open", use_container_width=True, type="primary"):
                if selected_file == "(new file)":
                    _new_file()
                else:
                    _load_file(selected_file)
                st.rerun()
        with col_refresh:
            if st.button(
                "↺ Refresh",
                use_container_width=True,
                help="Re-scan CONFIG_DIR for inventory files",
            ):
                st.rerun()

        st.divider()
        st.subheader("About")
        st.markdown(
            "Inventory files define phoneme and symbol sets used by the FST parser. "
            "Each node can contain **phones** (consonants, vowels, tones) or **flags** "
            "(internal markers). See `README.md` for the full schema."
        )

    # ── Guard: no state yet ────────────────────────────────────────────────
    if "editor_state" not in st.session_state:
        st.info(
            "👈 Select a file in the sidebar and click **Open**, or open a **(new file)** to begin."
        )
        st.stop()

    editor_state: EditorState = st.session_state.editor_state

    # ── Header row ────────────────────────────────────────────────────────
    title_label = editor_state.path or "New inventory file"
    st.header(title_label)

    col_path, col_spacer = st.columns([3, 5])
    with col_path:
        st.text_input(
            "File path (relative to CONFIG_DIR)",
            key="path",
            value=editor_state.path,
            placeholder="inventory/segments.yaml",
            help="Must be inside an `inventory/` directory, e.g. `inventory/segments.yaml`",
        )

    # ── Top-level toolbar ─────────────────────────────────────────────────
    col_add, col_save, col_preview_toggle, _ = st.columns([1.4, 1.2, 1.6, 5])

    with col_add:
        if st.button("➕ Add top-level node", use_container_width=True):
            _insert_top_node()
            st.rerun()

    with col_save:
        if st.button("💾 Save YAML", use_container_width=True, type="primary"):
            try:
                # TODO implement save function!
                # depends on YAML serialization logic
                st.toast(f"✅ Saved to `{editor_state.path}`", icon="✅")
            except ValueError as exc:
                st.error(str(exc))

    with col_preview_toggle:
        show_preview = st.toggle("Show YAML preview", value=False)

    # ── YAML preview ──────────────────────────────────────────────────────
    if show_preview:
        with st.container(border=True):
            st.caption("YAML preview — reflects unsaved edits")
            # TODO implement YAML serialization

    st.divider()

    # ── Node tree ─────────────────────────────────────────────────────────
    top_node_ids = editor_state.data["node_id_map"]["item"]

    if not top_node_ids:
        st.info(
            "No nodes yet. Click **➕ Add top-level node** to start — "
            "for example a `consonants` or `vowels` category."
        )
    else:
        for node_id in top_node_ids:
            _render_node(node_id, depth=0)


if __name__ == "__main__":
    inventory_page()
