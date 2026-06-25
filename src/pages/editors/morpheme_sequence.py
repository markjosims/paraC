"""
Streamlit Morpheme Sequence Editor
==================================
A UI for creating and editing MorphemeSequence YAML configs.
"""

from __future__ import annotations
import uuid
import streamlit as st

from src.grammar import Grammar
from src.grammar.registry.feature_values_registry import Feature
from src.grammar.orchestrator.feature_orchestrator import FeatureOrchestrator
from src.pages.editors.editor_base import EditorBase
from src.validation import validate_file_reference_str, validate_pattern
from src.widgets import (
    render_editor_guard,
    render_editor_header,
    render_editor_sidebar,
    render_editor_toolbar,
)

_config_kind = "MorphemeSequence"
_config_key = "morpheme_sequence_configs"

# Prefix constants
_STEP_TYPE_PREFIX = "step-type-"
_STEP_VAL_PREFIX = "step-val-"
_REMOVE_STEP_PREFIX = "remove-step-"
_MOVE_UP_PREFIX = "move-up-"
_MOVE_DOWN_PREFIX = "move-down-"
_FIXED_FEAT_NAME_PREFIX = "fixed-feat-name-"
_FIXED_FEAT_VAL_PREFIX = "fixed-feat-val-"
_REMOVE_FIXED_FEAT_PREFIX = "remove-fixed-feat-"

_MORPHEME_TYPES = ["Lexicon", "Paradigm", "Pattern", "Rule", "MorphemeSet"]

_help_str = """
Morpheme Sequence files define a sequence of morphemes (Lexicons, Paradigms, Patterns, or Rules)
to be concatenated or composed to form fully inflected words.
"""


class MorphemeSequenceEditor(EditorBase):
    """
    Editor for MorphemeSequence YAML configs.

    self.data keys:
        steps — list[dict] (uuid, type, value)
    """

    def __init__(self) -> None:
        super().__init__(kind=_config_kind, config_key=_config_key)

    def build_state_from_config(self, config_object: dict) -> dict:
        grammar: Grammar = st.session_state.grammar
        feature_orchestrator: FeatureOrchestrator = grammar.feature_orchestrator

        raw_data = config_object.get("data", [])
        steps = []
        for step in raw_data:
            steps.append(
                {
                    "uuid": str(uuid.uuid4()),
                    "type": step.get("type", "Lexicon"),
                    "value": step.get("value", ""),
                }
            )
        fixed_features = []
        for f_name, f_val in config_object.get("fixed_features", {}).items():
            feat = feature_orchestrator.get_feature(f_name)
            fixed_features.append(
                {
                    "uuid": str(uuid.uuid4()),
                    "feature": feat,
                    "value": f_val,
                }
            )
        return {
            "steps": steps,
            "fixed_features": fixed_features,
        }

    def read_form_to_state(self) -> None:
        """Sync widget values back to self.data."""
        self.clear_errors()
        for step in self.data["steps"]:
            uid = step["uuid"]
            s_type = self.get_node_widget(_STEP_TYPE_PREFIX, uid)
            s_val = self.get_node_widget(_STEP_VAL_PREFIX, uid)
            if s_type is not None:
                step["type"] = s_type
            if s_val is not None:
                step["value"] = s_val
                if s_type == "morpheme":
                    validate_pattern(self.add_error, s_val, f"Morpheme '{s_val}'")

        for ff in self.data["fixed_features"]:
            uid = ff["uuid"]
            feat = self.get_node_widget(_FIXED_FEAT_NAME_PREFIX, uid)
            f_val = self.get_node_widget(_FIXED_FEAT_VAL_PREFIX, uid)
            if feat is not None:
                ff["feature"] = feat
            if f_val is not None:
                ff["value"] = f_val

    def to_yaml(self) -> dict:
        output_data = []
        for step in self.data["steps"]:
            output_data.append(
                {
                    "type": step["type"],
                    "value": step["value"],
                }
            )
        fixed_features = {}
        for ff in self.data["fixed_features"]:
            feat: Feature = ff["feature"]
            if feat:
                fixed_features[feat.name] = ff["value"]

        return {
            "kind": self.kind,
            "fixed_features": fixed_features if fixed_features else None,
            "data": output_data,
        }

    def get_default_data(self) -> dict:
        return {
            "steps": [],
            "fixed_features": [],
        }

    def insert_step(self) -> None:
        self.data["steps"].append(
            {
                "uuid": str(uuid.uuid4()),
                "type": "Lexicon",
                "value": "",
            }
        )

    def remove_step(self, uid: str) -> None:
        self.data["steps"] = [s for s in self.data["steps"] if s["uuid"] != uid]

    def move_step(self, uid: str, direction: str) -> None:
        steps = self.data["steps"]
        idx = next((i for i, s in enumerate(steps) if s["uuid"] == uid), -1)
        if idx == -1:
            return

        new_idx = idx - 1 if direction == "up" else idx + 1
        if 0 <= new_idx < len(steps):
            steps[idx], steps[new_idx] = steps[new_idx], steps[idx]

    def insert_fixed_feature(self) -> None:
        self.data["fixed_features"].append(
            {
                "uuid": str(uuid.uuid4()),
                "feature": "",
                "value": "",
            }
        )

    def remove_fixed_feature(self, uid: str) -> None:
        self.data["fixed_features"] = [
            ff for ff in self.data["fixed_features"] if ff["uuid"] != uid
        ]


def _render_step(
    step: dict,
    editor: MorphemeSequenceEditor,
    available_lexicons: list[str],
    available_paradigms: list[str],
    available_patterns: list[str],
    available_rules: list[str],
    available_morpheme_sets: list[str],
    index: int,
    total: int,
) -> None:
    uid = step["uuid"]
    with st.container(border=True):
        col_type, col_val, col_move, col_del = st.columns([1.5, 4, 0.8, 0.4])

        with col_type:
            st.selectbox(
                "Type",
                options=_MORPHEME_TYPES,
                index=(
                    _MORPHEME_TYPES.index(step["type"])
                    if step["type"] in _MORPHEME_TYPES
                    else 0
                ),
                key=editor.get_widget_key(_STEP_TYPE_PREFIX, uid),
                label_visibility="collapsed",
            )

        with col_val:
            s_type = step["type"]
            options = []
            if s_type == "Lexicon":
                options = available_lexicons
            elif s_type == "Paradigm":
                options = available_paradigms
            elif s_type == "Pattern":
                options = available_patterns
            elif s_type == "Rule":
                options = available_rules
            elif s_type == "MorphemeSet":
                options = available_morpheme_sets

            # Pattern can be inline, so allow text input if not in options
            if (
                s_type == "Pattern"
                and step["value"]
                and not step["value"].startswith("$")
                and step["value"] not in options
            ):
                st.text_input(
                    "Value",
                    value=step["value"],
                    key=editor.get_widget_key(_STEP_VAL_PREFIX, uid),
                    label_visibility="collapsed",
                )
            elif options:
                # Add current value to options if it's a ref but missing (maybe deleted or wrong kind)
                current_val = step["value"]
                all_opts = [""] + options
                if current_val and current_val not in all_opts:
                    all_opts.append(current_val)

                st.selectbox(
                    "Value",
                    options=all_opts,
                    index=all_opts.index(current_val) if current_val in all_opts else 0,
                    key=editor.get_widget_key(_STEP_VAL_PREFIX, uid),
                    label_visibility="collapsed",
                )
            else:
                st.text_input(
                    "Value",
                    value=step["value"],
                    key=editor.get_widget_key(_STEP_VAL_PREFIX, uid),
                    label_visibility="collapsed",
                    placeholder="Reference ($name) or inline pattern",
                )

        with col_move:
            m_up, m_down = st.columns(2)
            if m_up.button(
                "↑",
                key=editor.get_widget_key(_MOVE_UP_PREFIX, uid),
                disabled=(index == 0),
            ):
                editor.move_step(uid, "up")
                st.rerun()
            if m_down.button(
                "↓",
                key=editor.get_widget_key(_MOVE_DOWN_PREFIX, uid),
                disabled=(index == total - 1),
            ):
                editor.move_step(uid, "down")
                st.rerun()

        with col_del:
            if st.button(
                "✕",
                key=editor.get_widget_key(_REMOVE_STEP_PREFIX, uid),
                help="Remove step",
            ):
                editor.remove_step(uid)
                st.rerun()


def morpheme_sequence_page() -> None:
    st.set_page_config(
        page_title="Morpheme Sequence Editor",
        page_icon="🔗",
        layout="wide",
    )

    render_editor_sidebar(
        kind=_config_kind,
        editor_class=MorphemeSequenceEditor,
        config_key=_config_key,
        help_str=_help_str,
    )

    editor = render_editor_guard(kind=_config_kind)
    editor.read_form_to_state()
    render_editor_header(kind=_config_kind, editor=editor)

    grammar: Grammar = st.session_state.grammar
    available_lexicons = []
    available_paradigms = []
    available_patterns = []
    available_rules = []
    available_morpheme_sets = []
    available_features = []

    if grammar:
        available_features = sorted(
            list(grammar.feature_orchestrator.features.values())
        )
        available_lexicons = sorted(
            [
                validate_file_reference_str(name)
                for name in grammar.lexicon_registry.data.keys()
            ]
        )
        available_paradigms = sorted(
            [
                validate_file_reference_str(name)
                for name in grammar.paradigm_registry.data.keys()
            ]
        )
        available_patterns = sorted(
            [
                validate_file_reference_str(name)
                for name in grammar.fst_orchestrator.pattern_registry.data.keys()
            ]
        )
        available_rules = sorted(
            [
                validate_file_reference_str(name)
                for name in grammar.fst_orchestrator.rule_registry.data.keys()
            ]
        )
        available_morpheme_sets = sorted(
            [
                validate_file_reference_str(name)
                for name in grammar.morpheme_set_registry.data.keys()
            ]
        )

    toolbar_placeholder = st.empty()
    st.divider()

    # 1. Fixed Features
    with st.expander("Fixed Features", expanded=False):
        st.caption("Features that are fixed to specific values for this sequence.")
        fixed_features = editor.data.get("fixed_features", [])
        for ff in fixed_features:
            uid = ff["uuid"]
            fc1, fc2, fc3 = st.columns([2.5, 2.5, 0.4])
            with fc1:
                st.selectbox(
                    "Feature",
                    options=[""] + [feature.name for feature in available_features],
                    format_func=lambda f: f.name if isinstance(f, Feature) else f,
                    index=(
                        available_features.index(ff["feature"]) + 1
                        if ff.get("feature", None) in available_features
                        else 0
                    ),
                    key=editor.get_widget_key(_FIXED_FEAT_NAME_PREFIX, uid),
                    label_visibility="collapsed",
                )
            with fc2:
                # get values for selected feature
                feat_obj = None
                if ff.get("feature", None):
                    feat_obj = grammar.feature_orchestrator.get_feature(
                        ff.get("feature", None)
                    )
                f_vals = feat_obj.values if feat_obj else []
                st.selectbox(
                    "Value",
                    options=[""] + f_vals,
                    index=(
                        f_vals.index(ff["value"]) + 1 if ff["value"] in f_vals else 0
                    ),
                    key=editor.get_widget_key(_FIXED_FEAT_VAL_PREFIX, uid),
                    label_visibility="collapsed",
                )
            with fc3:
                if st.button("✕", key=f"del-ff-{uid}", help="Remove fixed feature"):
                    editor.remove_fixed_feature(uid)
                    st.rerun()
        if st.button("➕ Add fixed feature"):
            editor.insert_fixed_feature()
            st.rerun()

    # 2. Sequence Editor
    st.subheader("Sequence Steps")
    steps = editor.data.get("steps", [])
    if not steps:
        st.info("No steps yet. Click **➕ Add step** to start.")
    else:
        # Header for columns
        h1, h2, h3, h4 = st.columns([1.5, 4, 0.8, 0.4])
        h1.markdown("**Type**")
        h2.markdown("**Value (Reference or Inline Pattern)**")
        h3.markdown("**Move**")

        for i, step in enumerate(steps):
            _render_step(
                step,
                editor,
                available_lexicons,
                available_paradigms,
                available_patterns,
                available_rules,
                available_morpheme_sets,
                i,
                len(steps),
            )

    with toolbar_placeholder.container():
        render_editor_toolbar(
            editor, add_label="Add step", add_callback=editor.insert_step
        )


if __name__ == "__main__":
    morpheme_sequence_page()
