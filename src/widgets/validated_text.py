import streamlit as st
from src.pages.editors.editor_base import EditorBase
from typing import Callable

ErrorCallback = Callable[[str], None]
ValidationCallback = Callable[[str, ErrorCallback], None]


def validated_text_input(
    editor: EditorBase,
    label: str,
    prefix: str,
    node_id: str,
    value: str = "",
    suffix: str = "",
    placeholder: str = "",
    validation_fn: ValidationCallback | None = None,
    **kwargs,
) -> str:
    """
    Render a text input that validates on submission.
    """
    key = editor.get_widget_key(prefix, node_id, suffix)

    # st_keyup returns the current value
    val = st.text_input(
        label,
        value=value,
        key=key,
        placeholder=placeholder,
        **kwargs,
    )

    if validation_fn:
        # We want to track field-specific errors
        editor.field_errors.pop(key, None)

        def add_field_error(message: str) -> None:
            if key not in editor.field_errors:
                editor.field_errors[key] = message

        try:
            validation_fn(val, add_field_error)
        except Exception as e:
            editor.field_errors[key] = str(e)

    if key in editor.field_errors:
        st.error(editor.field_errors[key], icon="⚠️")

    return val
