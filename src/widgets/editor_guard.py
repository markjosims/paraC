import streamlit as st
from loguru import logger
from src.config_utils.schema_validation import ConfigKindType
from src.pages.editors.editor_base import EditorBase

def render_editor_guard(kind: ConfigKindType) -> EditorBase:
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
            editor.load_file(file_name)
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