"""
Streamlit Lexicon Editor
========================
A UI for creating and editing PartOfSpeech YAML configs and their associated CSV lexicons.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pandas as pd
import streamlit as st

from src.grammar import Grammar
from src.grammar.registry.feature_values_registry import Feature
from src.grammar.registry.lexicon_registry import PartOfSpeech
from src.grammar.registry.lexicon_registry import Lexicon
from src.pages.editors.editor_base import EditorBase
from src.widgets import (
    render_editor_guard,
    render_editor_header,
    render_editor_sidebar,
    render_editor_toolbar,
    validated_text_input,
    render_feature_multiselect,
)
from validation import validate_pattern

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

_help_str = """
Lexicon files define a Part of Speech (POS) and its associated vocabulary.
- **YAML**: Defines features, lexical features, and principal parts.
- **CSV**: Stores the actual word list (roots, glosses, and values for defined columns).
"""


class LexiconEditor(EditorBase):
    """
    Editor for PartOfSpeech YAML configs + CSV lexicon.

    self.data keys:
        name             — str
        features         — list[Feature]
        lexical_features — list[Feature]
        principal_parts  — list[str]
        rows             — list[dict] (uuid, root, gloss, + dynamic cols)
    """

    def __init__(self) -> None:
        super().__init__(kind=_config_kind, config_key=_config_key)

    def build_state_from_config(self, config_object: dict) -> dict:
        grammar: Grammar = st.session_state.grammar
        if grammar is None:
            st.error("Grammar not loaded. Cannot initialize lexicon.")
            st.stop()

        lexicon = Lexicon.from_config(
            config_object, grammar.feature_orchestrator, grammar.fst_orchestrator
        )
        pos = lexicon.part_of_speech

        rows = lexicon.entries.to_dict(orient="records")
        for r in rows:
            r["uuid"] = str(uuid.uuid4())

        return {
            "name": pos.name,
            "features": pos.features,
            "lexical_features": pos.lexical_features,
            "principal_parts": pos.principal_parts,
            "rows": rows,
        }

    def read_form_to_state(self) -> None:
        """Sync widget values back to self.data."""
        self.clear_errors()

        # Features are updated via feature_multiselect callback

        pp_text = st.session_state.get(
            self.get_widget_key(_PRINCIPAL_PARTS_PREFIX, "main"), ""
        )
        if pp_text is not None:
            self.data["principal_parts"] = [
                s.strip() for s in pp_text.split(",") if s.strip()
            ]

        # 2. Table Rows
        lexical_feature_names = [f.name for f in self.data["lexical_features"]]
        dynamic_cols = self.data["principal_parts"] + lexical_feature_names
        for row in self.data["rows"]:
            uid = row["uuid"]
            root = self.get_node_widget(_ROW_ROOT_PREFIX, uid)
            gloss = self.get_node_widget(_ROW_GLOSS_PREFIX, uid)
            if root is not None:
                row["root"] = root
                validate_pattern(self.add_error, root, f"Root '{root}'")
            if gloss is not None:
                row["gloss"] = gloss

            for col in dynamic_cols:
                val = self.get_node_widget(_ROW_COL_PREFIX, uid, suffix=col)
                if val is not None:
                    row[col] = val
                    if col in self.data["principal_parts"] and val:
                        validate_pattern(
                            self.add_error,
                            val,
                            f"Principal Part '{col}' for root '{root}'",
                        )

    def to_yaml(self) -> dict:

        grammar: Grammar = st.session_state.grammar
        if grammar is None:
            st.error("Grammar not loaded. Cannot serialize part of speech.")
            st.stop()

        pos = PartOfSpeech(
            name=self.stem,
            features=self.data["features"],
            lexical_features=self.data["lexical_features"],
            principal_parts=self.data["principal_parts"],
        )
        return pos.to_dict()

    def get_default_data(self) -> dict:
        return {
            "name": "",
            "features": [],
            "lexical_features": [],
            "principal_parts": [],
            "rows": [],
        }

    def save(self, stem: str) -> None:
        """Saves both the YAML config and the CSV lexicon."""
        # Ensure name matches stem
        self.data["name"] = stem

        # 1. Save YAML via Base
        super().save(stem)

        # 2. Save CSV
        lexical_feature_names = [f.name for f in self.data["lexical_features"]]
        dynamic_cols = self.data["principal_parts"] + lexical_feature_names
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
        lexical_feature_names = [f.name for f in self.data["lexical_features"]]
        dynamic_cols = self.data["principal_parts"] + lexical_feature_names
        new_row = {"uuid": str(uuid.uuid4()), "root": "", "gloss": ""}
        for col in dynamic_cols:
            new_row[col] = ""
        self.data["rows"].append(new_row)

    def remove_row(self, uid: str) -> None:
        self.data["rows"] = [r for r in self.data["rows"] if r["uuid"] != uid]


def _render_lexicon_row(
    row: dict,
    dynamic_cols: list[str],
    lexical_features: list[Feature],
    editor: LexiconEditor,
    grammar: Grammar,
) -> None:
    uid = row["uuid"]
    # root, gloss, dynamic cols, delete btn
    num_cols = 2 + len(dynamic_cols)
    cols = st.columns([1.5, 1.5] + [1.2] * len(dynamic_cols) + [0.4])

    with cols[0]:
        validated_text_input(
            editor,
            "Root",
            _ROW_ROOT_PREFIX,
            uid,
            value=row["root"],
            label_visibility="collapsed",
            validation_fn=lambda v, add_error: validate_pattern(
                add_error, v, f"Root '{v}'"
            ),
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
            feat_obj = next((f for f in lexical_features if f.name == col), None)
            if feat_obj and grammar:
                # Use selectbox for lexical features
                options = feat_obj.values
                st.selectbox(
                    col,
                    options=[""] + options,
                    index=(
                        options.index(row.get(col)) + 1
                        if row.get(col) in options
                        else 0
                    ),
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
        if st.button(
            "✕", key=editor.get_widget_key(_REMOVE_ROW_PREFIX, uid), help="Delete row"
        ):
            editor.remove_row(uid)
            st.rerun()


def lexicon_page() -> None:
    st.set_page_config(
        page_icon="📖",
        layout="wide",
    )

    render_editor_sidebar(
        kind=_config_kind,
        editor_class=LexiconEditor,
        config_key=_config_key,
        help_str=_help_str,
    )

    editor = render_editor_guard(kind=_config_kind)
    editor.read_form_to_state()
    render_editor_header(kind=_config_kind, editor=editor)

    grammar: Grammar = st.session_state.grammar

    # 1. Config section
    with st.expander(
        "POS Configuration",
        expanded=st.session_state.get(f"expanded-pos-{editor.scope}", True),
    ):
        st.session_state[f"expanded-pos-{editor.scope}"] = (
            False  # default to collapsed after first show
        )
        col1, col2 = st.columns(2)
        with col1:
            render_feature_multiselect(
                "Inflected Features",
                editor,
                _FEATURES_PREFIX,
                data_key="features",
            )
        with col2:
            render_feature_multiselect(
                "Lexical Features",
                editor,
                _LEXICAL_FEATURES_PREFIX,
                data_key="lexical_features",
            )

        st.text_input(
            "Principal Parts (comma-separated columns)",
            value=", ".join(editor.data["principal_parts"]),
            key=editor.get_widget_key(_PRINCIPAL_PARTS_PREFIX, "main"),
            help="These columns will be added to the lexicon table below.",
            on_change=st.rerun,  # Force table refresh
        )

    toolbar_placeholder = st.empty()
    st.divider()

    # 2. Entries table
    lexical_feature_names = [f.name for f in editor.data["lexical_features"]]
    dynamic_cols = editor.data["principal_parts"] + lexical_feature_names

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
            _render_lexicon_row(
                row, dynamic_cols, editor.data["lexical_features"], editor, grammar
            )

    with toolbar_placeholder.container():
        render_editor_toolbar(
            editor=editor,
            add_label="Add lexicon row",
            add_callback=editor.insert_row,
        )


if __name__ == "__main__":
    lexicon_page()
