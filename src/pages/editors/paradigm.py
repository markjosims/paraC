"""
Streamlit Paradigm Editor
=========================
A UI for creating and editing Paradigm YAML configs.
"""

from __future__ import annotations

import uuid
from typing import Literal
import streamlit as st
from pathlib import Path

from src.grammar import Grammar
from src.grammar.registry.feature_values_registry import Feature
from src.grammar.orchestrator.feature_orchestrator import FeatureOrchestrator
from src.grammar.registry.feature_marker_registry import Marker
from src.pages.editors.editor_base import EditorBase
from src.grammar.registry.paradigm_registry import Paradigm
from src.grammar.registry.feature_marker_registry import MarkerList
from src.validation import validate_file_reference_str
from src.widgets import (
    render_editor_guard,
    render_editor_header,
    render_editor_sidebar,
    render_editor_toolbar,
    render_marker_list,
    sync_marker_list,
)

_config_kind = "Paradigm"
_config_key = "paradigm_configs"

# Prefix constants
_POS_PREFIX = "pos-select-"
_ORDER_STAGE_PREFIX = "order-stage-"
_FEATURE_MAPPING_NAME_PREFIX = "fm-name-"
_FEATURE_MAPPING_MODE_PREFIX = "fm-mode-"
_FEATURE_MAPPING_VALUE_PREFIX = "fm-val-"
_COMBO_REF_PREFIX = "combo-ref-"
_CONTINGENT_REF_PREFIX = "contingent-ref-"
_LF_FILTER_NAME_PREFIX = "lf-filter-name-"
_LF_FILTER_VAL_PREFIX = "lf-filter-val-"
_PATTERN_FILTER_PREFIX = "pattern-filter-"
_REMOVE_ORDER_PREFIX = "remove-order-"
_REMOVE_FM_PREFIX = "remove-fm-"
_REMOVE_CM_PREFIX = "remove-cm-"
_REMOVE_LF_PREFIX = "remove-lf-"

_help_str = """
Paradigm files define how multiple features combine to realize inflected forms.
It orchestrates feature markers, contingent markers, and lexical filters.
"""


class ParadigmEditor(EditorBase):
    """
    Editor for Paradigm YAML configs.
    """

    def __init__(self) -> None:
        super().__init__(kind=_config_kind, config_key=_config_key)

    def build_state_from_config(self, config_object: dict) -> dict:
        grammar: Grammar = st.session_state.grammar
        feature_orchestrator: FeatureOrchestrator = grammar.feature_orchestrator

        # 1. Basics
        pos = config_object.get("part_of_speech", "")
        marker_order = config_object.get("order", [])
        order_stages = [{"uuid": str(uuid.uuid4()), "name": s} for s in marker_order]

        # 2. Global Markers
        gm_raw = config_object.get("global_markers", [])
        if isinstance(gm_raw, dict):
            gm_raw = [gm_raw]
        global_markers = [Marker.from_config(m) for m in gm_raw]

        # 3. Feature Mappings
        fm_raw = config_object.get("feature_markers", {})
        feature_mappings = []
        for f_name, m_str in fm_raw.items():
            mode = "null"
            val = ""
            if m_str is not None:
                if isinstance(m_str, str) and m_str.startswith("$"):
                    mode = "ref"
                    val = m_str
                else:
                    mode = "fixed"
                    val = str(m_str)

            feature = feature_orchestrator.get_feature(f_name)
            feature_mappings.append(
                {
                    "uuid": str(uuid.uuid4()),
                    "feature": feature,
                    "mode": mode,
                    "value": val,
                }
            )

        # 4. Combinations & Contingent
        combo_ref = config_object.get("feature_value_combinations", "")
        cm_refs = [
            {"uuid": str(uuid.uuid4()), "ref": r}
            for r in config_object.get("contingent_markers", [])
        ]

        # 5. Filters
        filter_cfg = config_object.get("filter", {})
        pattern_filter = filter_cfg.get("pattern", "")
        lf_filters = []
        for pair in filter_cfg.get("lexical_features", []):
            if len(pair) == 2:
                feat = feature_orchestrator.get_feature(pair[0])
                lf_filters.append(
                    {
                        "uuid": str(uuid.uuid4()),
                        "feature": feat,
                        "feature_value": pair[1],
                    }
                )

        return {
            "part_of_speech": pos,
            "order_stages": order_stages,
            "global_markers": global_markers,
            "feature_mappings": feature_mappings,
            "feature_value_combinations": combo_ref,
            "contingent_markers": cm_refs,
            "pattern_filter": pattern_filter,
            "lexical_feature_filters": lf_filters,
        }

    def read_form_to_state(self) -> None:
        """Sync widget values back to self.data."""
        # Top-level
        part_of_speech = st.session_state.get(self.get_widget_key(_POS_PREFIX, "main"))
        if part_of_speech is not None:
            self.data["part_of_speech"] = part_of_speech

        feature_combo = st.session_state.get(
            self.get_widget_key(_COMBO_REF_PREFIX, "main")
        )
        if feature_combo is not None:
            self.data["feature_value_combinations"] = validate_file_reference_str(
                feature_combo
            )

        pattern = st.session_state.get(
            self.get_widget_key(_PATTERN_FILTER_PREFIX, "main")
        )
        if pattern is not None:
            self.data["pattern_filter"] = pattern

        # Order Stages
        for stage in self.data["order_stages"]:
            name = self.get_node_widget(_ORDER_STAGE_PREFIX, stage["uuid"])
            if name is not None:
                stage["name"] = name

        # Global Markers
        sync_marker_list(self, self.data["global_markers"], "global")

        # Feature Mappings
        for feature_mappings in self.data["feature_mappings"]:
            uid = feature_mappings["uuid"]
            feature = self.get_node_widget(_FEATURE_MAPPING_NAME_PREFIX, uid)
            mode = self.get_node_widget(_FEATURE_MAPPING_MODE_PREFIX, uid)
            val = self.get_node_widget(_FEATURE_MAPPING_VALUE_PREFIX, uid)
            if feature is not None:
                feature_mappings["feature"] = feature
            if mode is not None:
                feature_mappings["mode"] = mode
            if val is not None:
                if mode == "ref":
                    val = validate_file_reference_str(val)
                feature_mappings["value"] = val

        # Contingent refs
        for contingent_markers in self.data["contingent_markers"]:
            ref = st.session_state.get(
                self.get_widget_key(_CONTINGENT_REF_PREFIX, contingent_markers["uuid"])
            )
            if ref is not None:
                contingent_markers["ref"] = validate_file_reference_str(ref)

        # LF Filters
        for lexical_feature_filter in self.data["lexical_feature_filters"]:
            uid = lexical_feature_filter["uuid"]
            feature = self.get_node_widget(_LF_FILTER_NAME_PREFIX, uid)
            val = self.get_node_widget(_LF_FILTER_VAL_PREFIX, uid)
            if feature is not None:
                lexical_feature_filter["feature"] = feature
            if val is not None:
                lexical_feature_filter["feature_value"] = val

    def to_yaml(self) -> dict:
        breakpoint()
        self.read_form_to_state()

        grammar: Grammar = st.session_state.grammar
        if grammar is None:
            st.error("Grammar not loaded. Cannot serialize paradigm.")
            st.stop()

        marker_orchestrator = grammar.marker_orchestrator
        lexicon_registry = grammar.lexicon_registry
        fst_orchestrator = grammar.fst_orchestrator

        # Get actual objects from registry by their source path stem (matched from self.data modes)
        markers = []
        fixed_features = {}
        for feature_mapping in self.data["feature_mappings"]:
            feature: Feature = feature_mapping["feature"]
            if not feature:
                continue
            if feature_mapping["mode"] == "ref":
                ref_name = feature_mapping["value"].removeprefix("$")
                markers.append(marker_orchestrator.get_feature_markers(ref_name))
            elif feature_mapping["mode"] == "fixed":
                fixed_features[feature.name] = feature_mapping["value"]
            # mode="null" is handled by ContingentMarkers

        contingent_markers = []
        for contingent_marker in self.data["contingent_markers"]:
            if contingent_marker["ref"]:
                ref_name = contingent_marker["ref"].removeprefix("$")
                contingent_markers.append(
                    marker_orchestrator.get_contingent_markers(ref_name)
                )

        lexicon = lexicon_registry.get_lexicon(self.data["part_of_speech"])

        feature_value_combinations = None
        if self.data["feature_value_combinations"]:
            ref_name = self.data["feature_value_combinations"].removeprefix("$")
            feature_value_combinations = marker_orchestrator.get_feature_combinations(
                ref_name
            )

        fixed_lexical_features = []
        for lf in self.data["lexical_feature_filters"]:
            if lf["feature"] and lf["feature_value"]:
                fixed_lexical_features.append((lf["feature"], lf["feature_value"]))

        paradigm = Paradigm(
            name=self.stem,
            markers=markers,
            contingent_markers=contingent_markers,
            lexicon=lexicon,
            fst_orchestrator=fst_orchestrator,
            pattern_filter=self.data["pattern_filter"] or None,
            fixed_lexical_features=fixed_lexical_features,
            fixed_features=fixed_features,
            marker_order=[s["name"] for s in self.data["order_stages"] if s["name"]],
            feature_value_combinations=feature_value_combinations,
            global_markers=MarkerList(self.data["global_markers"]),
        )
        return paradigm.to_dict()

    def get_default_data(self) -> dict:
        return {
            "part_of_speech": "",
            "order_stages": [],
            "global_markers": [],
            "feature_mappings": [],
            "feature_value_combinations": "",
            "contingent_markers": [],
            "pattern_filter": "",
            "lexical_feature_filters": [],
        }

    def insert_order_stage(self) -> None:
        self.data["order_stages"].append({"uuid": str(uuid.uuid4()), "name": ""})

    def remove_order_stage(self, uid: str) -> None:
        self.data["order_stages"] = [
            s for s in self.data["order_stages"] if s["uuid"] != uid
        ]

    def move_order_stage(self, uid: str, direction: Literal["up", "down"]) -> None:
        """Move an order stage up or down in the list."""
        stages = self.data["order_stages"]
        idx = next((i for i, s in enumerate(stages) if s["uuid"] == uid), -1)
        if idx == -1:
            return

        new_idx = idx - 1 if direction == "up" else idx + 1
        if 0 <= new_idx < len(stages):
            stages[idx], stages[new_idx] = stages[new_idx], stages[idx]

    def insert_feature_mapping(self) -> None:
        self.data["feature_mappings"].append(
            {"uuid": str(uuid.uuid4()), "feature_name": "", "mode": "ref", "value": ""}
        )

    def remove_feature_mapping(self, uid: str) -> None:
        self.data["feature_mappings"] = [
            f for f in self.data["feature_mappings"] if f["uuid"] != uid
        ]

    def insert_contingent_ref(self) -> None:
        self.data["contingent_markers"].append({"uuid": str(uuid.uuid4()), "ref": ""})

    def remove_contingent_ref(self, uid: str) -> None:
        self.data["contingent_markers"] = [
            c for c in self.data["contingent_markers"] if c["uuid"] != uid
        ]

    def insert_lf_filter(self) -> None:
        self.data["lexical_feature_filters"].append(
            {"uuid": str(uuid.uuid4()), "feature_name": "", "feature_value": ""}
        )

    def remove_lf_filter(self, uid: str) -> None:
        self.data["lexical_feature_filters"] = [
            lf for lf in self.data["lexical_feature_filters"] if lf["uuid"] != uid
        ]


@st.fragment
def _render_paradigm_config(
    available_pos: list[str],
    available_feature_combos: list[str],
    available_patterns: list[str],
    available_rules: list[str],
    available_principal_parts: list[str],
    available_feature_markers: list[str],
    available_contingent_markers: list[str],
    available_features: list[Feature],
    editor: EditorBase,
) -> None:
    # 1. Basics & Configuration
    with st.expander("Configuration", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.selectbox(
                "Part of Speech",
                options=[""] + available_pos,
                index=(
                    available_pos.index(editor.data["part_of_speech"]) + 1
                    if editor.data["part_of_speech"] in available_pos
                    else 0
                ),
                key=editor.get_widget_key(_POS_PREFIX, "main"),
            )
        with c2:
            st.selectbox(
                "Feature Combinations",
                options=[""] + available_feature_combos,
                index=(
                    available_feature_combos.index(
                        editor.data["feature_value_combinations"]
                    )
                    + 1
                    if editor.data["feature_value_combinations"]
                    in available_feature_combos
                    else 0
                ),
                key=editor.get_widget_key(_COMBO_REF_PREFIX, "main"),
            )
        with c3:
            st.selectbox(
                "Pattern Filter",
                options=[""] + available_patterns,
                index=(
                    available_patterns.index(editor.data["pattern_filter"]) + 1
                    if editor.data["pattern_filter"] in available_patterns
                    else 0
                ),
                key=editor.get_widget_key(_PATTERN_FILTER_PREFIX, "main"),
            )

    # 2. Order Stages
    with st.expander("Order Stages"):
        st.caption("Ordered stages of application. Markers should reference these.")
        for i, stage in enumerate(editor.data["order_stages"]):
            sc1, sc2, sc3, sc4 = st.columns([5, 0.5, 0.5, 0.5])
            with sc1:
                st.text_input(
                    "Stage name",
                    value=stage["name"],
                    key=editor.get_widget_key(_ORDER_STAGE_PREFIX, stage["uuid"]),
                    label_visibility="collapsed",
                )
            with sc2:
                if st.button(
                    "↑", key=f"up-{stage['uuid']}", disabled=(i == 0), help="Move up"
                ):
                    editor.move_order_stage(stage["uuid"], "up")
                    st.rerun()
            with sc3:
                if st.button(
                    "↓",
                    key=f"down-{stage['uuid']}",
                    disabled=(i == len(editor.data["order_stages"]) - 1),
                    help="Move down",
                ):
                    editor.move_order_stage(stage["uuid"], "down")
                    st.rerun()
            with sc4:
                if st.button(
                    "✕", key=f"del-stage-{stage['uuid']}", help="Remove stage"
                ):
                    editor.remove_order_stage(stage["uuid"])
                    st.rerun()
        if st.button("➕ Add order stage"):
            editor.insert_order_stage()
            st.rerun()

    # 3. Global Markers
    with st.expander("Global Markers"):
        render_marker_list(
            editor,
            editor.data["global_markers"],
            "global",
            available_rules,
            available_principal_parts,
            label="",
        )

    # 4. Feature Mappings
    with st.expander("Feature Mappings", expanded=True):
        st.caption("Map features to specific marker sets or fixed values.")
        for fm in editor.data["feature_mappings"]:
            uid = fm["uuid"]
            with st.container(border=True):
                mc1, mc2, mc3, mc4 = st.columns([2, 1.5, 3, 0.4])
                with mc1:
                    st.selectbox(
                        "Feature",
                        options=[""] + available_features,
                        format_func=lambda f: f.name if isinstance(f, Feature) else f,
                        index=(
                            available_features.index(fm["feature"]) + 1
                            if fm["feature"] in available_features
                            else 0
                        ),
                        key=editor.get_widget_key(_FEATURE_MAPPING_NAME_PREFIX, uid),
                    )
                with mc2:
                    mode = st.selectbox(
                        "Source",
                        options=["ref", "fixed", "null"],
                        index=["ref", "fixed", "null"].index(fm["mode"]),
                        format_func=lambda x: {
                            "ref": "Marker Set",
                            "fixed": "Fixed Value",
                            "null": "Contingent Only",
                        }[x],
                        key=editor.get_widget_key(_FEATURE_MAPPING_MODE_PREFIX, uid),
                    )
                with mc3:
                    if mode == "ref":
                        st.selectbox(
                            "Value",
                            options=[""] + available_feature_markers,
                            index=(
                                available_feature_markers.index(fm["value"]) + 1
                                if fm["value"] in available_feature_markers
                                else 0
                            ),
                            key=editor.get_widget_key(
                                _FEATURE_MAPPING_VALUE_PREFIX, uid
                            ),
                        )
                    elif mode == "fixed":
                        st.text_input(
                            "Value",
                            value=fm["value"],
                            key=editor.get_widget_key(
                                _FEATURE_MAPPING_VALUE_PREFIX, uid
                            ),
                        )
                    else:
                        st.write("Marked via Contingent Markers only.")
                with mc4:
                    if st.button("✕", key=f"del-fm-{uid}"):
                        editor.remove_feature_mapping(uid)
                        st.rerun()
        if st.button("➕ Add feature mapping"):
            editor.insert_feature_mapping()
            st.rerun()

    # 5. Contingent Markers
    with st.expander("Contingent Markers"):
        for cm in editor.data["contingent_markers"]:
            cc1, cc2 = st.columns([5, 1])
            with cc1:
                st.selectbox(
                    "Ref",
                    options=[""] + available_contingent_markers,
                    index=(
                        available_contingent_markers.index(cm["ref"]) + 1
                        if cm["ref"] in available_contingent_markers
                        else 0
                    ),
                    key=editor.get_widget_key(_CONTINGENT_REF_PREFIX, cm["uuid"]),
                    label_visibility="collapsed",
                )
            with cc2:
                if st.button("✕", key=f"del-cm-{cm['uuid']}"):
                    editor.remove_contingent_ref(cm["uuid"])
                    st.rerun()
        if st.button("➕ Add contingent marker ref"):
            editor.insert_contingent_ref()
            st.rerun()

    # 6. Lexical Filters
    with st.expander("Lexical Feature Filters"):
        for lf in editor.data["lexical_feature_filters"]:
            uid = lf["uuid"]
            lc1, lc2, lc3 = st.columns([2.5, 2.5, 0.4])
            with lc1:
                st.selectbox(
                    "Lexical Feature",
                    options=[""] + available_features,
                    format_func=lambda f: f.name if isinstance(f, Feature) else f,
                    index=(
                        available_features.index(lf["feature"]) + 1
                        if lf["feature"] in available_features
                        else 0
                    ),
                    key=editor.get_widget_key(_LF_FILTER_NAME_PREFIX, uid),
                    label_visibility="collapsed",
                )
            with lc2:
                # get values for selected feature
                feat_obj: Feature = lf["feature"]
                l_vals = feat_obj.values if feat_obj else []
                st.selectbox(
                    "Value",
                    options=[""] + l_vals,
                    index=(
                        l_vals.index(lf["feature_value"]) + 1
                        if lf["feature_value"] in l_vals
                        else 0
                    ),
                    key=editor.get_widget_key(_LF_FILTER_VAL_PREFIX, uid),
                    label_visibility="collapsed",
                )


def paradigm_page() -> None:
    st.set_page_config(page_title="Paradigm Editor", page_icon="🏗️", layout="wide")

    render_editor_sidebar(_config_kind, ParadigmEditor, _config_key, _help_str)
    editor = render_editor_guard(kind=_config_kind)
    render_editor_header(kind=_config_kind, editor=editor)

    grammar: Grammar = st.session_state.grammar
    available_pos = []
    available_features = []
    available_rules = []
    available_principal_parts = []
    available_feature_markers = []
    available_contingent_markers = []
    available_feature_combos = []
    available_patterns = []

    if grammar:
        config_walker = st.session_state.get("config_walker")
        available_pos = sorted(
            [
                validate_file_reference_str(Path(f).stem)
                for f in config_walker.config_filemap["part_of_speech_configs"]
            ]
        )
        available_features = sorted(
            list(grammar.feature_orchestrator.features.values())
        )
        available_rules = list(grammar.fst_orchestrator.rule_registry.data.keys())
        principal_part_sets = set()
        for pos_config in grammar.lexicon_registry.config_objects.values():
            for col in pos_config.get("columns", []):
                principal_part_sets.add(col)
        available_principal_parts = sorted(list(principal_part_sets))
        available_feature_markers = sorted(
            [
                validate_file_reference_str(Path(f).stem)
                for f in config_walker.config_filemap["feature_marker_configs"]
            ]
        )
        available_contingent_markers = sorted(
            [
                validate_file_reference_str(Path(f).stem)
                for f in config_walker.config_filemap[
                    "contingent_feature_marker_configs"
                ]
            ]
        )
        available_feature_combos = sorted(
            [
                validate_file_reference_str(Path(f).stem)
                for f in config_walker.config_filemap["feature_combination_configs"]
            ]
        )
        available_patterns = sorted(
            list(grammar.fst_orchestrator.pattern_registry.data.keys())
        )

    toolbar_placeholder = st.empty()
    with toolbar_placeholder.container():
        render_editor_toolbar(editor)

    _render_paradigm_config(
        editor=editor,
        available_contingent_markers=available_contingent_markers,
        available_feature_combos=available_feature_combos,
        available_feature_markers=available_feature_markers,
        available_principal_parts=available_principal_parts,
        available_patterns=available_patterns,
        available_features=available_features,
        available_rules=available_rules,
        available_pos=available_pos,
    )


if __name__ == "__main__":
    paradigm_page()
