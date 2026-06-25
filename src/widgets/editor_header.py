import streamlit as st
from loguru import logger
from src.pages.editors.editor_base import EditorBase
from src.config_utils.schema_validation import ConfigKindType


def render_editor_header(kind: ConfigKindType, editor: EditorBase) -> None:
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

    if editor.errors:
        for error in editor.errors:
            st.error(error)

