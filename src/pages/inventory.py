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

import glob
import os
from pathlib import Path

import streamlit as st
from src.grammar.registry.inventory_registry import (
    InventoryItem,
    InventoryClass,
    InventoryMemberType,
    InventoryRegistry,
)
from src.grammar import Grammar
from src.config_utils.config_walker import ConfigWalker
from src.pages.editor_utils import EditorState
import yaml

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

# TODO: remove all `_editor` logic and refactor to be internal to this script
# or come from the new editor_utils.py file
# TODO: use new InventoryItem/Class API
# InventoryItem is only leaf nodes
# Only InventoryClass is to be rendered: phone/flag leaf nodes
# are built from CSVs in form for InventoryClass
# and stored internally

# Editor logic:
# .load_state(dirpath, relpath) ->: {path, kind, nodes}
# .new_state() ->: {path, kind, nodes}
# .update_from_form() ->: {path: updated_path, nodes: self._update_items_from_form}
# ._update_items_from_form() ->: recursively serialize nodes
# .add_item(item: dict) ->: append item to self.nodes
# .to_yaml() ->: serialize nodes using ._mapping_from_nodes
# ._mapping_from_nodes(nodes_list) ->:
#   - splits commas
#   - changes DIAC tokens into actual diacritics

_config_kind = "Inventory"
_config_key = "inventory_configs"

# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------


def _load_file(filepath: str) -> None:
    """Load an inventory file into session state, clearing stale widget keys."""
    _clear_node_widget_keys(st.session_state.get("editor_state", {}).get("nodes", []))
    config_walker: ConfigWalker = st.session_state["config_walker"]
    try:
        config_object = config_walker.config_data[_config_key][filepath]
        inventory_reg = InventoryRegistry(config_objects={filepath: config_object})
        item_map = inventory_reg.data
        top_items = inventory_reg.top_items
        state = EditorState(
            path=filepath,
            kind=_config_kind,
            data={"item_map": item_map, "top_items": top_items},
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
    _clear_node_widget_keys(st.session_state.get("editor_state", {}).get("nodes", []))
    st.session_state.editor_state = EditorState(path="", kind=_config_kind)
    st.session_state.loaded_file = None
    # also reset the path widget
    st.session_state.pop("path", None)


def _clear_node_widget_keys(nodes: list[InventoryMemberType]) -> None:
    """Remove all widget keys for a node subtree from session state."""
    for node in nodes:
        nid = node["id"]
        for prefix in ("name-", "ref-", "items_kind-", "items_text-"):
            st.session_state.pop(f"{prefix}{nid}", None)
        for i in range(len(DIAC_TOKENS)):
            st.session_state.pop(f"diac-{nid}-{i}", None)
        _clear_node_widget_keys(node.get("children", []))


def _sync_to_state() -> dict:
    """
    Pull current widget values (from st.session_state) into a fresh copy of
    the editor state. st.session_state.get() satisfies the form interface
    expected by InventoryEditor.update_from_form().
    """
    return _editor.update_from_form(st.session_state.editor_state, st.session_state)


def _yaml_preview(state: dict) -> str:
    try:
        synced = _sync_to_state()
        return _editor.to_yaml(synced)
    except Exception:
        return _editor.to_yaml(state)


# ---------------------------------------------------------------------------
# Node rendering (recursive)
# ---------------------------------------------------------------------------


def _render_node(node_id: str, node: InventoryItem, depth: int = 0) -> None:
    """Render a single inventory node and recurse into children."""
    has_children = bool(node.children)

    # Visual indentation: pair an invisible spacer column with the content column.
    if depth > 0:
        indent_ratio = min(depth * 0.035, 0.25)
        _, content_col = st.columns([indent_ratio, 1.0 - indent_ratio])
    else:
        content_col = st

    node_ref = node.get("ref", "(ref not set)")
    with content_col.popover(f"{node_name} `{node_ref}`"):
        # ── Name & Reference ──────────────────────────────────────────────
        col_name, col_ref = st.columns(2)
        with col_name:
            st.text_input(
                "Node name",
                key=f"name-{nid}",
                value=node["name"],
                placeholder="consonants",
            )
        with col_ref:
            st.text_input(
                "Reference",
                key=f"ref-{nid}",
                value=node["ref"],
                placeholder="<C>",
            )

        # ── Items (phones / flags) — disabled when node has children ──────
        if has_children:
            st.text_input(
                "Node contents",
                value="Child nodes",
                disabled=True,
                key=f"_disabled-{nid}",
            )
            st.caption("This node has children — phones and flags are disabled.")
        else:
            col_kind, col_items = st.columns(2)
            with col_kind:
                kind_options = ["phones", "flags"]
                st.selectbox(
                    "Item type",
                    options=kind_options,
                    index=kind_options.index(node.get("items_kind", "phones")),
                    key=f"items_kind-{nid}",
                )
            with col_items:
                st.text_input(
                    "Items",
                    key=f"items_text-{nid}",
                    value=node.get("items_text", ""),
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
                    # if diac_cols[i].button(token, key=f"diac-{nid}-{i}"):
                    # current = st.session_state.get(f"items_text-{nid}", "")
                    # separator = ", " if current.strip() and not current.rstrip().endswith(",") else ""
                    # st.session_state[f"items_text-{nid}"] = current + separator + token
                    # st.rerun()

        # ── Node actions ──────────────────────────────────────────────────
        btn_add, btn_remove = st.columns(2)
        with btn_add:
            if st.button("＋ Add child", key=f"add-child-{nid}"):
                updated = _sync_to_state()
                updated = _editor.add_child_node(updated, nid)
                st.session_state.editor_state = updated
                st.rerun()
        with btn_remove:
            if st.button("✕ Delete item", key=f"remove-{nid}"):
                updated = _sync_to_state()
                updated = _editor.remove_item(updated, nid)
                st.session_state.editor_state = updated
                st.rerun()

    # Render children below the parent box, each with one additional level of indent.
    for child in node.get("children", []):
        _render_node(child, depth + 1)


# ---------------------------------------------------------------------------
# Page layout
# ---------------------------------------------------------------------------


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
                    _load_file(config_dir, selected_file)
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

    state: dict = st.session_state.editor_state

    # ── Header row ────────────────────────────────────────────────────────
    title_label = state.get("path") or "New inventory file"
    st.header(title_label)

    col_path, col_spacer = st.columns([3, 5])
    with col_path:
        st.text_input(
            "File path (relative to CONFIG_DIR)",
            key="path",
            value=state.get("path", ""),
            placeholder="inventory/segments.yaml",
            help="Must be inside an `inventory/` directory, e.g. `inventory/segments.yaml`",
        )

    # ── Top-level toolbar ─────────────────────────────────────────────────
    col_add, col_save, col_preview_toggle, _ = st.columns([1.4, 1.2, 1.6, 5])

    with col_add:
        if st.button("➕ Add top-level node", use_container_width=True):
            updated = _sync_to_state()
            updated = _editor.add_item(updated)
            st.session_state.editor_state = updated
            st.rerun()

    with col_save:
        if st.button("💾 Save YAML", use_container_width=True, type="primary"):
            updated = _sync_to_state()
            # pull the current path widget value
            updated["path"] = st.session_state.get(
                "path", updated.get("path", "")
            ).strip()
            try:
                saved_path = _editor.save(config_dir, updated)
                st.session_state.editor_state = updated
                st.session_state.loaded_file = saved_path
                st.toast(f"✅ Saved to `{saved_path}`", icon="✅")
            except ValueError as exc:
                st.error(str(exc))

    with col_preview_toggle:
        show_preview = st.toggle("Show YAML preview", value=False)

    # ── YAML preview ──────────────────────────────────────────────────────
    if show_preview:
        with st.container(border=True):
            st.caption("YAML preview — reflects unsaved edits")
            st.code(_yaml_preview(state), language="yaml")

    st.divider()

    # ── Node tree ─────────────────────────────────────────────────────────
    nodes: list[dict] = state.get("nodes", [])

    if not nodes:
        st.info(
            "No nodes yet. Click **➕ Add top-level node** to start — "
            "for example a `consonants` or `vowels` category."
        )
    else:
        for node in nodes:
            _render_node(node, depth=0)


if __name__ == "__main__":
    inventory_page()
