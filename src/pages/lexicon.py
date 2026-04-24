"""
Streamlit Lexicon Editor
========================
A UI for creating and editing PartOfSpeech YAML configs and their associated CSV lexicons.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
import yaml

from src.config_utils.config_walker import ConfigWalker
from src.grammar.registry.lexicon_registry import Lexicon, LexiconRegistry
from src.pages.editor_utils import (
    EditorBase,
    editor_guard,
    editor_header,
    editor_sidebar,
)

_config_kind = "PartOfSpeech"
_config_key = "part_of_speech_configs"

# Prefix constants
_FEATURES_PREFIX = "features-list-"
_LEXICAL_FEATURES_PREFIX = "lexical-features-list-"
_PRINCIPAL_PARTS_PREFIX = "principal-parts-"
_ROW_ROOT_PREFIX = "row-root-"
_ROW_GLOSS_PREFIX = "row-gloss-"
_ROW_COL_PREFIX = "row-col-"
_REMOVE_ROW_PREFIX = "remove-row-"

_WIDGET_PREFIXES: list[str] = [
    _FEATURES_PREFIX,
    _LEXICAL_FEATURES_PREFIX,
    _PRINCIPAL_PARTS_PREFIX,
    _ROW_ROOT_PREFIX,
    _ROW_GLOSS_PREFIX,
    _ROW_COL_PREFIX,
    _REMOVE_ROW_PREFIX,
]

_help_str = """
Lexicon files define a Part of Speech (POS) and its associated vocabulary.
- **YAML**: Defines features, lexical features, and principal parts.
- **CSV**: Stores the actual word list (roots, glosses, and values for defined columns).
"""


class LexiconEditor(EditorBase):
    """
    Editor for PartOfSpeech YAML configs + CSV lexicons.

    self.data keys:
        name             — str
        features         — list[str]
        lexical_features — list[str]
        principal_parts  — list[str]
        rows             — list[dict] (uuid, root, gloss, + dynamic cols)
    """

    def __init__(self) -> None:
        super().__init__(kind=_config_kind, config_key=_config_key)

    def build_state_from_config(self, config_object: dict) -> dict:
        grammar = st.session_state.get("grammar")
        if grammar is None:
            st.error("Grammar not loaded. Cannot initialize lexicon.")
            st.stop()

        lexicon = Lexicon.from_config(config_object, grammar.feature_orchestrator)
        pos = lexicon.part_of_speech

        rows = lexicon.entries.to_dict(orient="records")
        for r in rows:
            r["uuid"] = str(uuid.uuid4())

        return {
            "name": pos.name,
            "features": [f.name for f in pos.features],
            "lexical_features": [f.name for f in pos.lexical_features],
            "principal_parts": pos.principal_parts,
            "rows": rows,
        }

    def read_form_to_state(self) -> None:
        """Sync widget values back to self.data."""
        # 1. POS Settings
        features = st.session_state.get(self.get_widget_key(_FEATURES_PREFIX, "main"), [])
        if features:
            self.data["features"] = features

        lexical_features = st.session_state.get(
            self.get_widget_key(_LEXICAL_FEATURES_PREFIX, "main"), []
        )
        if lexical_features:
            self.data["lexical_features"] = lexical_features

        pp_text = st.session_state.get(
            self.get_widget_key(_PRINCIPAL_PARTS_PREFIX, "main"), ""
        )
        if pp_text is not None:
            self.data["principal_parts"] = [
                s.strip() for s in pp_text.split(",") if s.strip()
            ]

        # 2. Table Rows
        dynamic_cols = self.data["principal_parts"] + self.data["lexical_features"]
        for row in self.data["rows"]:
            uid = row["uuid"]
            root = self.get_node_widget(_ROW_ROOT_PREFIX, uid)
            gloss = self.get_node_widget(_ROW_GLOSS_PREFIX, uid)
            if root is not None:
                row["root"] = root
            if gloss is not None:
                row["gloss"] = gloss

            for col in dynamic_cols:
                val = self.get_node_widget(_ROW_COL_PREFIX, uid, suffix=col)
                if val is not None:
                    row[col] = val

    def to_yaml(self) -> dict:
        return {
            "kind": self.kind,
            "name": self.stem,  # Use filename as POS name
            "features": self.data["features"],
            "lexical_features": self.data["lexical_features"],
            "principal_parts": self.data["principal_parts"],
        }

    def save(self, stem: str) -> None:
        """Saves both the YAML config and the CSV lexicon."""
        # Ensure name matches stem
        self.data["name"] = stem

        # 1. Save YAML via Base
        super().save(stem)

        # 2. Save CSV
        dynamic_cols = self.data["principal_parts"] + self.data["lexical_features"]
        save_cols = ["root", "gloss"] + dynamic_cols
        
        # Prepare DataFrame
        df_data = []
        for r in self.data["rows"]:
            df_row = {col: r.get(col, "") for col in save_cols}
            df_data.append(df_row)
        
        df = pd.DataFrame(df_data)
        csv_path = Path(self.config_dir) / "lexicon" / f"{stem}.csv"
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(csv_path, index=False)

    def insert_row(self) -> None:
        dynamic_cols = self.data["principal_parts"] + self.data["lexical_features"]
        new_row = {"uuid": str(uuid.uuid4()), "root": "", "gloss": ""}
        for col in dynamic_cols:
            new_row[col] = ""
        self.data["rows"].append(new_row)

    def remove_row(self, uid: str) -> None:
        self.data["rows"] = [r for r in self.data["rows"] if r["uuid"] != uid]


def _render_lexicon_row(
    row: dict, dynamic_cols: list[str], lexical_features: list[str], editor: LexiconEditor, grammar: Any
) -> None:
    uid = row["uuid"]
    # root, gloss, dynamic cols, delete btn
    num_cols = 2 + len(dynamic_cols)
    cols = st.columns([1.5, 1.5] + [1.2] * len(dynamic_cols) + [0.4])

    with cols[0]:
        st.text_input(
            "Root",
            value=row["root"],
            key=editor.get_widget_key(_ROW_ROOT_PREFIX, uid),
            label_visibility="collapsed",
        )
    with cols[1]:
        st.text_input(
            "Gloss",
            value=row["gloss"],
            key=editor.get_widget_key(_ROW_GLOSS_PREFIX, uid),
            label_visibility="collapsed",
        )

    for i, col in enumerate(dynamic_cols):
        with cols[i + 2]:
            if col in lexical_features and grammar:
                # Use selectbox for lexical features
                options = grammar.feature_orchestrator.feature_values_registry.features_to_values.get(col, [])
                st.selectbox(
                    col,
                    options=[""] + options,
                    index=options.index(row.get(col)) + 1 if row.get(col) in options else 0,
                    key=editor.get_widget_key(_ROW_COL_PREFIX, uid, suffix=col),
                    label_visibility="collapsed",
                )
            else:
                st.text_input(
                    col,
                    value=row.get(col, ""),
                    key=editor.get_widget_key(_ROW_COL_PREFIX, uid, suffix=col),
                    label_visibility="collapsed",
                )

    with cols[-1]:
        if st.button("✕", key=editor.get_widget_key(_REMOVE_ROW_PREFIX, uid), help="Delete row"):
            editor.read_form_to_state()
            editor.remove_row(uid)
            st.rerun()


def lexicon_toolbar(editor: LexiconEditor) -> None:
    col_add, col_save, col_preview_toggle, _ = st.columns([1.4, 1.2, 1.6, 5])

    with col_add:
        if st.button("➕ Add lexicon row", use_container_width=True):
            editor.read_form_to_state()
            editor.insert_row()
            st.rerun()

    with col_save:
        if st.button("💾 Save (YAML + CSV)", use_container_width=True, type="primary"):
            stem = st.session_state.get("file_name", "").strip()
            if not stem:
                st.error("Enter a file name before saving.")
            else:
                try:
                    editor.save(stem)
                    st.toast(f"✅ Saved `{stem}.yaml` and `{stem}.csv`", icon="✅")
                except (ValueError, OSError) as exc:
                    st.error(str(exc))

    with col_preview_toggle:
        show_preview = st.toggle("Show YAML preview", value=False)

    if show_preview:
        editor.read_form_to_state()
        with st.container(border=True):
            st.caption("YAML preview — reflects unsaved edits")
            st.code(yaml.dump(editor.to_yaml(), allow_unicode=True, sort_keys=False))


def lexicon_page() -> None:
    st.set_page_config(
        page_title="Lexicon Editor",
        page_icon="📖",
        layout="wide",
    )

    config_dir: str = st.session_state["config_dir"]
    config_walker: ConfigWalker = st.session_state["config_walker"]
    pos_files = config_walker.config_filemap[_config_key]

    editor_sidebar(
        kind=_config_kind,
        editor_class=LexiconEditor,
        config_dir=config_dir,
        config_walker=config_walker,
        kind_files=pos_files,
        help_str=_help_str,
    )

    editor = editor_guard(kind=_config_kind)
    editor_header(kind=_config_kind, editor=editor)

    grammar = st.session_state.get("grammar")
    available_features = []
    if grammar:
        available_features = list(
            grammar.feature_orchestrator.feature_values_registry.features_to_values.keys()
        )

    # 1. Config section
    with st.expander("POS Configuration", expanded=not bool(editor.data["rows"])):
        col1, col2 = st.columns(2)
        with col1:
            current_f = editor.data["features"]
            sel_f = st.multiselect(
                "Inflected Features",
                options=available_features or current_f,
                default=current_f,
                key=editor.get_widget_key(_FEATURES_PREFIX, "main"),
            )
            if sel_f != current_f:
                editor.read_form_to_state()
                st.rerun()
        with col2:
            current_lf = editor.data["lexical_features"]
            sel_lf = st.multiselect(
                "Lexical Features",
                options=available_features or current_lf,
                default=current_lf,
                key=editor.get_widget_key(_LEXICAL_FEATURES_PREFIX, "main"),
            )
            if sel_lf != current_lf:
                editor.read_form_to_state()
                st.rerun()

        st.text_input(
            "Principal Parts (comma-separated columns)",
            value=", ".join(editor.data["principal_parts"]),
            key=editor.get_widget_key(_PRINCIPAL_PARTS_PREFIX, "main"),
            help="These columns will be added to the lexicon table below.",
            on_change=st.rerun # Force table refresh
        )

    toolbar_placeholder = st.empty()
    st.divider()

    # 2. Entries table
    dynamic_cols = editor.data["principal_parts"] + editor.data["lexical_features"]
    
    # Table Header
    header_cols = st.columns([1.5, 1.5] + [1.2] * len(dynamic_cols) + [0.4])
    header_cols[0].markdown("**Root**")
    header_cols[1].markdown("**Gloss**")
    for i, col in enumerate(dynamic_cols):
        header_cols[i + 2].markdown(f"**{col}**")

    if not editor.data["rows"]:
        st.info("No lexicon entries yet. Click **➕ Add lexicon row** to start.")
    else:
        for row in editor.data["rows"]:
            _render_lexicon_row(row, dynamic_cols, editor.data["lexical_features"], editor, grammar)

    with toolbar_placeholder.container():
        lexicon_toolbar(editor)


if __name__ == "__main__":
    lexicon_page()
