from src.pages.editors.editor_base import EditorBase, clear_all_editor_widget_keys
import streamlit as st
from loguru import logger
from pathlib import Path


def render_editor_sidebar(
    kind: str,
    editor_class: type[EditorBase],
    config_key: str,
    help_str: str,
) -> None:
    """
    Render sidebar for the editor page, including file selector and about info.
    """
    config_walker = st.session_state.get("config_walker")
    if config_walker is None:
        st.error("Config walker not found in session state.")
        st.stop()

    config_dir = str(config_walker.config_dir)
    kind_files = config_walker.config_filemap.get(config_key, [])

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
