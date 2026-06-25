from src.grammar import Grammar
from src.grammar.registry.feature_values_registry import Feature
from src.pages.editors.editor_base import EditorBase


import streamlit as st


def render_feature_multiselect(
    label: str,
    editor: EditorBase,
    key_prefix: str,
    help_str: str = "",
    data_key: str = "features",
) -> list[Feature]:
    """
    Standardized multiselect for picking morphological features.
    Handles loading available features from the grammar,
    updating editor state, and triggering st.rerun() on change.
    """
    grammar: Grammar = st.session_state.get("grammar")
    available_features = []
    if grammar:
        available_features = sorted(
            list(grammar.feature_orchestrator.features.values())
        )

    current_selection = editor.data.get(data_key, [])

    # Ensure current selection is also available in options if not in grammar (unlikely but safe)
    options = available_features
    if not available_features and current_selection:
        options = sorted(current_selection)

    selected = st.multiselect(
        label,
        options=options,
        format_func=lambda f: f.name,
        default=current_selection,
        key=editor.get_widget_key(key_prefix, "main"),
        help=help_str,
    )

    if selected != current_selection:
        editor.data[data_key] = selected
        st.rerun()

    return selected