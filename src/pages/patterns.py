"""
Streamlit Pattern Editor
========================
A UI for creating and editing pattern YAML configs.

Requires:
    CONFIG_DIR  — environment variable pointing to the config root directory.
                  All YAML files with kind: Patterns are auto-discovered from
                  that directory (recursive glob).

Usage:
    CONFIG_DIR=/path/to/configs streamlit run src/streamlit/app.py
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from src.config_utils.config_walker import ConfigWalker
from src.grammar import Grammar
from src.grammar.registry.pattern_registry import Pattern, PatternRegistry
from src.grammar.orchestrator.fst_orchestrator import FstOrchestrator
from src.pages.editor_utils import EditorBase, editor_guard, editor_sidebar, editor_header

_config_kind = "Patterns"
_config_key = "pattern_configs"

_NAME_PREFIX = "name-"
_REF_PREFIX = "ref-"
_PATTERN_TEXT_PREFIX = "pattern_text-"
_TEST_INCLUDES_PREFIX = "test_includes-"
_TEST_EXCLUDES_PREFIX = "test_excludes-"
_TEST_BUTTON_PREFIX = "test_button-"
_REMOVE_PREFIX = "remove-"
_WIDGET_PREFIXES: list[str] = [
    _NAME_PREFIX,
    _REF_PREFIX,
    _PATTERN_TEXT_PREFIX,
    _TEST_INCLUDES_PREFIX,
    _TEST_EXCLUDES_PREFIX,
    _TEST_BUTTON_PREFIX,
    _REMOVE_PREFIX,
]

_help_str = """
Pattern files define FSA shorthands used in morphological rules.
Each entry has a **reference** (e.g. `<V_Front>`) and a **pattern**
string (a regex-like expression over inventory refs).
Patterns are displayed in dependency order.
"""

"""
PatternEditor
"""


class PatternEditor(EditorBase):
    """
    Editor for Patterns YAML configs.

    self.data keys:
        patterns     — list[Pattern] in topological display order
        id_map       — dict[uuid, Pattern] for stable widget keying
        test_results — dict[uuid, Any] populated by run_tests()
    """

    def __init__(self) -> None:
        super().__init__(kind=_config_kind, config_key=_config_key)

    # ------------------------------------------------------------------
    # EditorBase abstract methods
    # ------------------------------------------------------------------

    def build_state_from_config(self, config_object: dict) -> dict:
        filepath = config_object["source_path"]
        registry = PatternRegistry(config_objects={filepath: config_object})
        # patterns_sorted gives topological order (dependencies first)
        id_map: dict[str, Pattern] = {p.uuid: p for p in registry.patterns_sorted}
        return {
            "patterns": list(id_map.values()),
            "id_map": id_map,
            "test_results": {},
        }

    def read_form_to_state(self) -> None:
        """
        Sync widget values from st.session_state back into Pattern objects.
        Clears cached test results for any pattern whose ref or value changed.
        """
        id_map: dict[str, Pattern] = self.data.get("id_map", {})
        test_results: dict[str, Any] = self.data.get("test_results", {})

        for uid, pattern in id_map.items():
            old_ref = pattern._ref
            old_value = pattern.value

            name_val = self.get_node_widget(_NAME_PREFIX, uid)
            ref_val = self.get_node_widget(_REF_PREFIX, uid)
            pattern_val = self.get_node_widget(_PATTERN_TEXT_PREFIX, uid)
            includes_val = self.get_node_widget(_TEST_INCLUDES_PREFIX, uid)
            excludes_val = self.get_node_widget(_TEST_EXCLUDES_PREFIX, uid)

            if name_val is not None:
                pattern.name = name_val
            if ref_val is not None:
                pattern._ref = ref_val
            if pattern_val is not None:
                pattern.value = pattern_val
            if includes_val is not None:
                pattern.test_includes = [
                    s.strip() for s in includes_val.split(",") if s.strip()
                ]
            if excludes_val is not None:
                pattern.test_excludes = [
                    s.strip() for s in excludes_val.split(",") if s.strip()
                ]

            # invalidate cached test results if the pattern definition changed
            if pattern._ref != old_ref or pattern.value != old_value:
                test_results.pop(uid, None)

    def to_yaml(self) -> dict:
        patterns: list[Pattern] = self.data.get("patterns", [])
        return {
            "kind": self.kind,
            "patterns": [p.to_dict() for p in patterns],
        }

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def insert_pattern(self) -> str:
        """Append a blank pattern at the bottom; return its uuid."""
        new_pattern = Pattern(name="", value="", _ref="<new_ref>")
        self.data["id_map"][new_pattern.uuid] = new_pattern
        self.data["patterns"].append(new_pattern)
        return new_pattern.uuid

    def remove_pattern(self, uid: str) -> Pattern:
        """Remove pattern by uuid, clear its widget keys."""
        pattern = self.data["id_map"].pop(uid)
        self.data["patterns"].remove(pattern)
        self.data["test_results"].pop(uid, None)
        for prefix in _WIDGET_PREFIXES:
            st.session_state.pop(f"{prefix}{uid}", None)
        return pattern

    def run_tests(self, uid: str, grammar: Any) -> None:
        """
        Run include/exclude tests for the pattern identified by uid.
        Requires a loaded Grammar instance. Results are stored in
        self.data["test_results"][uid].
        """
        pattern = self.data["id_map"][uid]
        fst_orch: FstOrchestrator = grammar.fst_orchestrator
        results = fst_orch.test_pattern(
            pattern._ref,
            pattern.test_includes,
            pattern.test_excludes,
        )
        self.data["test_results"][uid] = results


"""
Pattern rendering
"""


def _render_pattern(uid: str, editor: PatternEditor) -> None:
    """Render a single pattern entry as an expandable card."""
    pattern: Pattern = editor.data["id_map"][uid]
    test_results = editor.data["test_results"].get(uid)

    ref_label = pattern._ref or "(ref not set)"
    name_label = pattern.name or "(unnamed)"

    with st.expander(f"{name_label} `{ref_label}`", expanded=False):
        col_name, col_ref = st.columns(2)
        with col_name:
            st.text_input(
                "Pattern name",
                key=editor.get_widget_key(_NAME_PREFIX, uid),
                value=pattern.name,
                placeholder="Front vowel",
            )
        with col_ref:
            st.text_input(
                "Reference",
                key=editor.get_widget_key(_REF_PREFIX, uid),
                value=pattern._ref,
                placeholder="<V_Front>",
            )

        st.text_input(
            "Pattern",
            key=editor.get_widget_key(_PATTERN_TEXT_PREFIX, uid),
            value=pattern.value,
            placeholder="(<e>|<i>|<ɛ>)",
            help="Regular expression string interpreted as an FSA.",
        )

        col_inc, col_exc = st.columns(2)
        with col_inc:
            st.text_input(
                "Test includes",
                key=editor.get_widget_key(_TEST_INCLUDES_PREFIX, uid),
                value=", ".join(pattern.test_includes),
                placeholder="e, i, ɛ",
                help="Comma-separated strings the pattern should accept.",
            )
        with col_exc:
            st.text_input(
                "Test excludes",
                key=editor.get_widget_key(_TEST_EXCLUDES_PREFIX, uid),
                value=", ".join(pattern.test_excludes),
                placeholder="a, o, u",
                help="Comma-separated strings the pattern should reject.",
            )

        col_test, col_remove = st.columns(2)
        with col_test:
            if st.button("▶ Run tests", key=editor.get_widget_key(_TEST_BUTTON_PREFIX, uid), use_container_width=True):
                grammar = st.session_state.get("grammar")
                if grammar is None:
                    st.warning("Grammar not loaded — cannot run tests.")
                else:
                    st.session_state["do_run_tests"] = uid
                    st.rerun()
        with col_remove:
            if st.button(
                "✕ Delete", key=editor.get_widget_key(_REMOVE_PREFIX, uid), use_container_width=True
            ):
                editor.remove_pattern(uid)
                st.rerun()

        # Test results
        if test_results is not None:
            results_list = test_results.get("results", [])
            all_pass = test_results.get("all_pass", False)
            if results_list:
                st.divider()
                badges = st.columns(len(results_list))
                for col, r in zip(badges, results_list):
                    icon = "✅" if r["pass"] else "❌"
                    col.markdown(
                        f"{icon} `{r['string']}`",
                        help=f"Type: {r.get('type', '?')}",
                    )
                if all_pass:
                    st.success("All tests pass")
                else:
                    st.error("Some tests failed")


"""
Page components
"""

def pattern_toolbar(editor: PatternEditor) -> None:
    col_add, col_save, col_preview_toggle, _ = st.columns([1.4, 1.2, 1.6, 5])

    with col_add:
        if st.button("➕ Add pattern", use_container_width=True):
            editor.insert_pattern()
            st.rerun()

    with col_save:
        if st.button("💾 Save YAML", use_container_width=True, type="primary"):
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
        show_preview = st.toggle("Show YAML preview", value=False)

    if show_preview:
        import yaml as _yaml
        with st.container(border=True):
            st.caption("YAML preview — reflects unsaved edits")
            st.code(
                _yaml.dump(editor.to_yaml(), allow_unicode=True, sort_keys=False)
            )

def pattern_form(editor: PatternEditor) -> None:
    """Render form inputs for all patterns in editor.data."""
    id_map: dict[str, Pattern] = editor.data.get("id_map", {})
    if not id_map:
        st.info(
            "No patterns yet. Click **➕ Add pattern** to start — "
            "for example a `Front vowel` or `Syllable` pattern."
        )
    else:
        for uid in id_map:
            _render_pattern(uid, editor)

"""
Page function
"""


def patterns_page() -> None:
    st.set_page_config(
        page_title="Pattern Editor",
        page_icon="🔣",
        layout="wide",
    )

    config_dir: str = st.session_state["config_dir"]
    config_walker: ConfigWalker = st.session_state["config_walker"]
    pattern_files = config_walker.config_filemap[_config_key]

    editor_sidebar(
        kind=_config_kind,
        editor_class=PatternEditor,
        config_dir=config_dir,
        config_walker=config_walker,
        kind_files=pattern_files,
        help_str=_help_str,
    )

    editor = editor_guard(kind=_config_kind)
    editor.read_form_to_state()

    # check if tests need to be run for a pattern (triggered by test button)
    if "do_run_tests" in st.session_state:
        uid: str = st.session_state.pop("do_run_tests")
        grammar: Grammar | None = st.session_state.get("grammar")
        if grammar is not None:
            editor.run_tests(uid, grammar)
            st.rerun()

    editor_header(kind=_config_kind, editor=editor)

    toolbar_placeholder = st.empty()

    st.divider()

    pattern_form(editor)

    with toolbar_placeholder.container():
        pattern_toolbar(editor)

    


if __name__ == "__main__":
    patterns_page()
