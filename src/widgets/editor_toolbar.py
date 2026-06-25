import streamlit as st
import yaml
from src.pages.editors.editor_base import EditorBase


def render_editor_toolbar(
    editor: EditorBase, add_label: str = "Add entry", add_callback: callable = None
) -> None:
    """Generic toolbar for Save, Preview, and Add actions."""
    col_add, col_save, col_preview_toggle, _ = st.columns([1.4, 1.2, 1.6, 5])

    with col_add:
        if add_callback and st.button(f"➕ {add_label}", use_container_width=True):
            add_callback()
            st.rerun()

    with col_save:
        if st.button(
            "💾 Save YAML",
            use_container_width=True,
            type="primary",
            disabled=not editor.is_valid,
        ):
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
        show_preview = st.toggle(
            "Show YAML preview", value=False, key=f"preview-toggle-{editor.scope}"
        )

    if show_preview and editor.is_valid:
        with st.container(border=True):
            st.caption("YAML preview — reflects unsaved edits")
            st.code(
                yaml.dump(
                    editor.to_yaml(),
                    allow_unicode=True,
                    sort_keys=False,
                ),
                language="yaml",
            )
    elif show_preview:
        st.warning("Errors detected: cannot render YAML preview.")
