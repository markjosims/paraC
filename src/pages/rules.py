"""
Streamlit Rules Editor
======================
A UI for creating and editing rule YAML configs.

Requires:
    CONFIG_DIR  — environment variable pointing to the config root directory.
                  All YAML files with kind: Rules are auto-discovered from
                  that directory (recursive glob).

Usage:
    CONFIG_DIR=/path/to/configs streamlit run src/streamlit/app.py
"""

from __future__ import annotations

from typing import Any, Literal

import streamlit as st
import yaml as _yaml

from src.config_utils.config_walker import ConfigWalker
from src.grammar.registry.rule_registry import Rule, RuleRegistry
from src.pages.editor_utils import EditorBase, editor_guard, editor_sidebar, editor_header

_config_kind = "Rules"
_config_key = "rule_configs"

_NAME_PREFIX = "name-"
_TYPE_PREFIX = "type-"
_DESC_PREFIX = "desc-"
_INPUT_PREFIX = "input-"
_OUTPUT_PREFIX = "output-"
_LEFT_CTX_PREFIX = "left_ctx-"
_RIGHT_CTX_PREFIX = "right_ctx-"
_DIRECTION_PREFIX = "direction-"
_STRING_MAP_PREFIX = "string_map-"
_RULE_SEQ_PREFIX = "rule_seq-"
_TEST_MAPPINGS_PREFIX = "test_mappings-"
_TEST_BUTTON_PREFIX = "test_button-"
_REMOVE_PREFIX = "remove-"
_CHANGE_TYPE_PREFIX = "change-type-"

_WIDGET_PREFIXES: list[str] = [
    _NAME_PREFIX,
    _TYPE_PREFIX,
    _DESC_PREFIX,
    _INPUT_PREFIX,
    _OUTPUT_PREFIX,
    _LEFT_CTX_PREFIX,
    _RIGHT_CTX_PREFIX,
    _DIRECTION_PREFIX,
    _STRING_MAP_PREFIX,
    _RULE_SEQ_PREFIX,
    _TEST_MAPPINGS_PREFIX,
    _TEST_BUTTON_PREFIX,
    _REMOVE_PREFIX,
    _CHANGE_TYPE_PREFIX,
]

_RULE_TYPES = ["simple_rule", "string_map", "rule_sequence"]
_DIRECTIONS = ["ltr", "rtl", "sim"]

_help_str = """
Rule files define phonological rewrite rules applied by the FST parser.
Each entry is one of:
- **Simple rule**: input/output pattern pair with optional left/right context.
- **String map**: explicit list of `input => output` pairs.
- **Rule sequence**: ordered chain of other rules applied in sequence.
"""


def _rule_to_dict(rule: Rule) -> dict:
    """Serialize a Rule to a YAML-serializable dict (config format)."""
    d: dict = {}

    if rule.description:
        d["description"] = rule.description

    if rule.type == "simple_rule":
        d["input_pattern"] = rule.input_pattern.value or ""
        d["output_pattern"] = rule.output_pattern.value or ""
        if rule.left_context.value:
            d["left_context"] = rule.left_context.value
        if rule.right_context.value:
            d["right_context"] = rule.right_context.value
        if rule.direction != "ltr":
            d["direction"] = rule.direction

    elif rule.type == "string_map":
        d["string_map"] = [
            [inp.value or "", out.value or ""]
            for inp, out in rule.string_map
        ]
        if rule.left_context.value:
            d["left_context"] = rule.left_context.value
        if rule.right_context.value:
            d["right_context"] = rule.right_context.value
        if rule.direction != "ltr":
            d["direction"] = rule.direction

    elif rule.type == "rule_sequence":
        d["rule_sequence"] = [r._ref for r in rule.rule_sequence]

    if rule.test_mappings:
        d["test_mappings"] = [list(pair) for pair in rule.test_mappings]

    return d


"""
RulesEditor
"""


class RulesEditor(EditorBase):
    """
    Editor for Rules YAML configs.

    self.data keys:
        rules        — list[Rule] in topological display order
        id_map       — dict[uuid, Rule]
        test_results — dict[uuid, Any] populated by run_tests()
    """

    def __init__(self) -> None:
        super().__init__(kind=_config_kind, config_key=_config_key)

    # ------------------------------------------------------------------
    # EditorBase abstract methods
    # ------------------------------------------------------------------

    def build_state_from_config(self, config_object: dict) -> dict:
        rule_configs = config_object["rules"]
        rules = [Rule.from_config(config) for config in rule_configs]
        id_map: dict[str, Rule] = {r.uuid: r for r in rules}
        return {
            "rules": list(id_map.values()),
            "id_map": id_map,
            "test_results": {},
        }

    def read_form_to_state(self) -> None:
        """
        Sync widget values from st.session_state back into Rule objects.
        Clears cached test results for any rule whose definition changed.
        """
        from src.fst_utils import Acceptor

        id_map: dict[str, Rule] = self.data.get("id_map", {})
        test_results: dict[str, Any] = self.data.get("test_results", {})

        for uid, rule in id_map.items():
            old_ref = rule._ref

            name_val = self.get_node_widget(_NAME_PREFIX, uid)
            desc_val = self.get_node_widget(_DESC_PREFIX, uid)

            if name_val is not None:
                rule._ref = name_val
                rule.value = name_val
            if desc_val is not None:
                rule.description = desc_val or None

            if rule.type == "simple_rule":
                inp = self.get_node_widget(_INPUT_PREFIX, uid)
                out = self.get_node_widget(_OUTPUT_PREFIX, uid)
                left = self.get_node_widget(_LEFT_CTX_PREFIX, uid)
                right = self.get_node_widget(_RIGHT_CTX_PREFIX, uid)
                direction = self.get_node_widget(_DIRECTION_PREFIX, uid)
                if inp is not None:
                    rule.input_pattern = Acceptor(inp)
                if out is not None:
                    rule.output_pattern = Acceptor(out)
                if left is not None:
                    rule.left_context = Acceptor(left)
                if right is not None:
                    rule.right_context = Acceptor(right)
                if direction is not None:
                    rule.direction = direction

            elif rule.type == "string_map":
                raw = self.get_node_widget(_STRING_MAP_PREFIX, uid)
                left = self.get_node_widget(_LEFT_CTX_PREFIX, uid)
                right = self.get_node_widget(_RIGHT_CTX_PREFIX, uid)
                direction = self.get_node_widget(_DIRECTION_PREFIX, uid)
                if raw is not None:
                    pairs = []
                    for line in raw.splitlines():
                        line = line.strip()
                        if "=>" in line:
                            parts = line.split("=>", 1)
                            pairs.append(
                                (Acceptor(parts[0].strip()), Acceptor(parts[1].strip()))
                            )
                    rule.string_map = pairs
                if left is not None:
                    rule.left_context = Acceptor(left)
                if right is not None:
                    rule.right_context = Acceptor(right)
                if direction is not None:
                    rule.direction = direction

            elif rule.type == "rule_sequence":
                raw = self.get_node_widget(_RULE_SEQ_PREFIX, uid)
                if raw is not None:
                    # resolve refs to Rule objects from id_map by _ref name
                    ref_map = {r._ref: r for r in id_map.values()}
                    seq = []
                    for line in raw.splitlines():
                        ref = line.strip()
                        if ref and ref in ref_map:
                            seq.append(ref_map[ref])
                    rule.rule_sequence = seq

            raw_mappings = self.get_node_widget(_TEST_MAPPINGS_PREFIX, uid)
            if raw_mappings is not None:
                mappings = []
                for line in raw_mappings.splitlines():
                    line = line.strip()
                    if "=>" in line:
                        parts = line.split("=>", 1)
                        mappings.append((parts[0].strip(), parts[1].strip()))
                rule.test_mappings = mappings

            if rule._ref != old_ref:
                test_results.pop(uid, None)

    def to_yaml(self) -> dict:
        rules: list[Rule] = self.data.get("rules", [])
        return {
            "kind": self.kind,
            "rules": {rule._ref: _rule_to_dict(rule) for rule in rules},
        }

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def insert_rule(self, rule_type: Literal["simple_rule", "string_map", "rule_sequence"] = "simple_rule") -> str:
        """Append a blank rule; return its uuid."""
        from src.fst_utils import Acceptor

        if rule_type == "simple_rule":
            new_rule = Rule(
                _ref="new_rule",
                type="simple_rule",
                input_pattern=Acceptor(""),
                output_pattern=Acceptor(""),
            )
        elif rule_type == "string_map":
            new_rule = Rule(
                _ref="new_rule",
                type="string_map",
                string_map=[(Acceptor("a"), Acceptor("b"))],
            )
        else:
            new_rule = Rule(
                _ref="new_rule",
                type="rule_sequence",
                rule_sequence=[],
            )

        self.data["id_map"][new_rule.uuid] = new_rule
        self.data["rules"].append(new_rule)
        return new_rule.uuid

    def remove_rule(self, uid: str) -> Rule:
        """Remove rule by uuid, clear its widget keys."""
        rule = self.data["id_map"].pop(uid)
        self.data["rules"].remove(rule)
        self.data["test_results"].pop(uid, None)
        for prefix in _WIDGET_PREFIXES:
            st.session_state.pop(f"{prefix}{uid}", None)
        return rule

    def change_rule_type(
        self,
        uid: str,
        new_type: Literal["simple_rule", "string_map", "rule_sequence"],
    ) -> None:
        """Change a rule's type and reset fields that are specific to the old type."""
        from src.fst_utils import Acceptor

        rule = self.data["id_map"].get(uid)
        if rule is None:
            raise ValueError(f"Rule {uid!r} does not exist.")

        if rule.type == new_type:
            return

        rule.type = new_type

        # Reset all type-specific state so the new form starts clean.
        rule.input_pattern = Acceptor("")
        rule.output_pattern = Acceptor("")
        rule.string_map = []
        rule.rule_sequence = []
        rule.left_context = Acceptor("")
        rule.right_context = Acceptor("")
        rule.direction = "ltr"
        rule.test_mappings = []
        self.data["test_results"].pop(uid, None)

        if new_type == "simple_rule":
            rule.input_pattern = Acceptor("")
            rule.output_pattern = Acceptor("")
        elif new_type == "string_map":
            rule.string_map = [(Acceptor("a"), Acceptor("b"))]
        elif new_type == "rule_sequence":
            rule.rule_sequence = []

        for prefix in (
            _INPUT_PREFIX,
            _OUTPUT_PREFIX,
            _LEFT_CTX_PREFIX,
            _RIGHT_CTX_PREFIX,
            _DIRECTION_PREFIX,
            _STRING_MAP_PREFIX,
            _RULE_SEQ_PREFIX,
            _TEST_MAPPINGS_PREFIX,
            _TEST_BUTTON_PREFIX,
        ):
            st.session_state.pop(editor_key := self.get_widget_key(prefix, uid), None)

    def run_tests(self, uid: str, grammar: Any) -> None:
        """
        Run test mappings for the rule identified by uid.
        Results are stored in self.data["test_results"][uid].
        """
        rule = self.data["id_map"][uid]
        fst_orch = grammar.fst_orchestrator
        results = fst_orch.test_rule(rule._ref, rule.test_mappings)
        self.data["test_results"][uid] = results


"""
Rule rendering
"""


def _render_rule(uid: str, editor: RulesEditor) -> None:
    """Render a single rule as an expandable card."""
    rule: Rule = editor.data["id_map"][uid]
    test_results = editor.data["test_results"].get(uid)

    ref_label = rule._ref or "(ref not set)"
    type_label = rule.type.replace("_", " ").title()

    with st.expander(f"`{ref_label}` — {type_label}", expanded=False):

        col_name, col_type = st.columns(2)
        with col_name:
            st.text_input(
                "Rule name",
                key=editor.get_widget_key(_NAME_PREFIX, uid),
                value=rule._ref,
                placeholder="coalesce_before_i",
            )
        with col_type:
            new_type = st.selectbox(
                "Rule type",
                options=_RULE_TYPES,
                index=_RULE_TYPES.index(rule.type) if rule.type in _RULE_TYPES else 0,
                format_func=lambda s: s.replace("_", " ").title(),
                key=editor.get_widget_key(_TYPE_PREFIX, uid),
            )
            st.button(
                "Change rule type",
                disabled=(new_type == rule.type),
                key=editor.get_widget_key(_CHANGE_TYPE_PREFIX, uid),
                on_click=editor.change_rule_type,
                args=(uid, new_type),
            )

        st.text_input(
            "Description",
            key=editor.get_widget_key(_DESC_PREFIX, uid),
            value=rule.description or "",
            placeholder="Short explanation of what this rule does",
        )

        # Type-specific fields
        if rule.type == "simple_rule":
            col_in, col_out = st.columns(2)
            with col_in:
                st.text_input(
                    "Input pattern",
                    key=editor.get_widget_key(_INPUT_PREFIX, uid),
                    value=rule.input_pattern.value or "",
                    placeholder="<V>-?",
                )
            with col_out:
                st.text_input(
                    "Output pattern",
                    key=editor.get_widget_key(_OUTPUT_PREFIX, uid),
                    value=rule.output_pattern.value or "",
                    placeholder="ɛ",
                )

            col_left, col_right = st.columns(2)
            with col_left:
                st.text_input(
                    "Left context",
                    key=editor.get_widget_key(_LEFT_CTX_PREFIX, uid),
                    value=rule.left_context.value or "",
                    placeholder="(<R>|<N>)",
                )
            with col_right:
                st.text_input(
                    "Right context",
                    key=editor.get_widget_key(_RIGHT_CTX_PREFIX, uid),
                    value=rule.right_context.value or "",
                    placeholder="<V>",
                )

            st.selectbox(
                "Direction",
                options=_DIRECTIONS,
                index=_DIRECTIONS.index(rule.direction) if rule.direction in _DIRECTIONS else 0,
                key=editor.get_widget_key(_DIRECTION_PREFIX, uid),
            )

        elif rule.type == "string_map":
            map_text = "\n".join(
                f"{inp.value or ''} => {out.value or ''}"
                for inp, out in rule.string_map
            )
            st.text_area(
                "String map",
                key=editor.get_widget_key(_STRING_MAP_PREFIX, uid),
                value=map_text,
                placeholder="o => ue\ne => ie",
                help="One `input => output` pair per line.",
                height=120,
            )

            col_left, col_right = st.columns(2)
            with col_left:
                st.text_input(
                    "Left context",
                    key=editor.get_widget_key(_LEFT_CTX_PREFIX, uid),
                    value=rule.left_context.value or "",
                    placeholder="(<R>|<N>)",
                )
            with col_right:
                st.text_input(
                    "Right context",
                    key=editor.get_widget_key(_RIGHT_CTX_PREFIX, uid),
                    value=rule.right_context.value or "",
                    placeholder="<V>",
                )

            st.selectbox(
                "Direction",
                options=_DIRECTIONS,
                index=_DIRECTIONS.index(rule.direction) if rule.direction in _DIRECTIONS else 0,
                key=editor.get_widget_key(_DIRECTION_PREFIX, uid),
            )

        elif rule.type == "rule_sequence":
            seq_text = "\n".join(r for r in rule.rule_sequence)
            id_map: dict[str, Rule] = editor.data["id_map"]
            available_refs = sorted(
                r._ref for r in id_map.values()
                if r.uuid != uid and r.type != "rule_sequence"
            )
            st.text_area(
                "Rule sequence",
                key=editor.get_widget_key(_RULE_SEQ_PREFIX, uid),
                value=seq_text,
                placeholder="\n".join(available_refs[:3]) if available_refs else "rule_a\nrule_b",
                help="One rule name per line, applied in order.",
                height=100,
            )
            if available_refs:
                st.caption("Available rules: " + ", ".join(f"`{r}`" for r in available_refs))

        # Test mappings (all rule types)
        if rule.type != "rule_sequence":
            mappings_text = "\n".join(
                f"{inp} => {out}" for inp, out in rule.test_mappings
            )
            st.text_area(
                "Test mappings",
                key=editor.get_widget_key(_TEST_MAPPINGS_PREFIX, uid),
                value=mappings_text,
                placeholder="oi => ɛ\nua => a",
                help="One `input => expected_output` pair per line.",
                height=80,
            )

        col_test, col_remove = st.columns(2)
        with col_test:
            if st.button(
                "▶ Run tests",
                key=editor.get_widget_key(_TEST_BUTTON_PREFIX, uid),
                use_container_width=True,
                disabled=(rule.type == "rule_sequence" or not rule.test_mappings),
            ):
                grammar = st.session_state.get("grammar")
                if grammar is None:
                    st.warning("Grammar not loaded — cannot run tests.")
                else:
                    editor.read_form_to_state()
                    editor.run_tests(uid, grammar)
                    st.rerun()
        with col_remove:
            if st.button(
                "✕ Delete",
                key=editor.get_widget_key(_REMOVE_PREFIX, uid),
                use_container_width=True,
            ):
                editor.remove_rule(uid)
                st.rerun()

        # Test results
        if test_results is not None:
            results_list = test_results.get("results", [])
            all_pass = test_results.get("all_pass", False)
            if results_list:
                st.divider()
                for r in results_list:
                    icon = "✅" if r["pass"] else "❌"
                    detail = (
                        f"`{r['input']}` → `{r['expected_output']}`"
                        if r["pass"]
                        else f"`{r['input']}` → `{'; '.join(r['output'])}` (expected `{r['expected_output']}`)"
                    )
                    st.markdown(f"{icon} {detail}")
                if all_pass:
                    st.success("All tests pass")
                else:
                    st.error("Some tests failed")


"""
Page components
"""


def rules_toolbar(editor: RulesEditor) -> None:
    col_add, col_save, col_preview_toggle, _ = st.columns([2.2, 1.2, 1.6, 4])

    with col_add:
        rule_type = st.selectbox(
            "New rule type",
            options=_RULE_TYPES,
            format_func=lambda s: s.replace("_", " ").title(),
            label_visibility="collapsed",
            key="new_rule_type_select",
        )
        if st.button("➕ Add rule", use_container_width=True):
            editor.insert_rule(rule_type)
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
        editor.read_form_to_state()
        with st.container(border=True):
            st.caption("YAML preview — reflects unsaved edits")
            st.code(_yaml.dump(editor.to_yaml(), allow_unicode=True, sort_keys=False))


def rules_form(editor: RulesEditor) -> None:
    """Render all rule cards."""
    id_map: dict[str, Rule] = editor.data.get("id_map", {})
    if not id_map:
        st.info(
            "No rules yet. Select a rule type and click **➕ Add rule** to start — "
            "for example a `simple_rule` rewrite or a `string_map`."
        )
    else:
        for uid in id_map:
            _render_rule(uid, editor)


"""
Page function
"""


def rules_page() -> None:
    st.set_page_config(
        page_title="Rules Editor",
        page_icon="📐",
        layout="wide",
    )

    config_dir: str = st.session_state["config_dir"]
    config_walker: ConfigWalker = st.session_state["config_walker"]
    rule_files = config_walker.config_filemap[_config_key]

    editor_sidebar(
        kind=_config_kind,
        editor_class=RulesEditor,
        config_dir=config_dir,
        config_walker=config_walker,
        kind_files=rule_files,
        help_str=_help_str,
    )

    editor = editor_guard(kind=_config_kind)
    editor_header(kind=_config_kind, editor=editor)

    toolbar_placeholder = st.empty()

    st.divider()

    rules_form(editor)

    with toolbar_placeholder.container():
        rules_toolbar(editor)


if __name__ == "__main__":
    rules_page()
