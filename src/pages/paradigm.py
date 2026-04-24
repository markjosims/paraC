"""
Streamlit Paradigm Editor
=========================
A UI for creating and editing Paradigm YAML configs.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

import streamlit as st
import yaml
from pathlib import Path

from src.config_utils.config_walker import ConfigWalker
from src.grammar.registry.feature_marker_registry import Marker
from src.pages.editor_utils import (
    EditorBase,
    editor_guard,
    editor_header,
    editor_sidebar,
    render_marker_list,
    MARKER_WIDGET_PREFIXES,
    _MARKER_TYPE_PREFIX,
    _MARKER_VALUE_PREFIX,
    _MARKER_REPLACE_IN_PREFIX,
    _MARKER_REPLACE_OUT_PREFIX,
    _MARKER_ORDER_PREFIX,
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

_WIDGET_PREFIXES: list[str] = [
    _POS_PREFIX,
    _ORDER_STAGE_PREFIX,
    _FEATURE_MAPPING_NAME_PREFIX,
    _FEATURE_MAPPING_MODE_PREFIX,
    _FEATURE_MAPPING_VALUE_PREFIX,
    _COMBO_REF_PREFIX,
    _CONTINGENT_REF_PREFIX,
    _LF_FILTER_NAME_PREFIX,
    _LF_FILTER_VAL_PREFIX,
    _PATTERN_FILTER_PREFIX,
    _REMOVE_ORDER_PREFIX,
    _REMOVE_FM_PREFIX,
    _REMOVE_CM_PREFIX,
    _REMOVE_LF_PREFIX,
] + MARKER_WIDGET_PREFIXES

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
        # 1. Basics
        pos = config_object.get("part_of_speech", "")
        marker_order = config_object.get("order", [])
        order_stages = [{"uuid": str(uuid.uuid4()), "name": s} for s in marker_order]
        
        # 2. Global Markers
        gm_raw = config_object.get("global_markers", [])
        if isinstance(gm_raw, dict): gm_raw = [gm_raw]
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
            feature_mappings.append({
                "uuid": str(uuid.uuid4()),
                "feature_name": f_name,
                "mode": mode,
                "value": val
            })
        
        # 4. Combinations & Contingent
        combo_ref = config_object.get("feature_value_combinations", "")
        cm_refs = [{"uuid": str(uuid.uuid4()), "ref": r} for r in config_object.get("contingent_markers", [])]

        # 5. Filters
        filter_cfg = config_object.get("filter", {})
        pattern_filter = filter_cfg.get("pattern", "")
        lf_filters = []
        for pair in filter_cfg.get("lexical_features", []):
            if len(pair) == 2:
                lf_filters.append({
                    "uuid": str(uuid.uuid4()),
                    "feature_name": pair[0],
                    "feature_value": pair[1]
                })

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
        pos = st.session_state.get(self.get_widget_key(_POS_PREFIX, "main"))
        if pos is not None: self.data["part_of_speech"] = pos
        
        combo = st.session_state.get(self.get_widget_key(_COMBO_REF_PREFIX, "main"))
        if combo is not None: self.data["feature_value_combinations"] = combo
        
        pattern = st.session_state.get(self.get_widget_key(_PATTERN_FILTER_PREFIX, "main"))
        if pattern is not None: self.data["pattern_filter"] = pattern

        # Order Stages
        for stage in self.data["order_stages"]:
            name = self.get_node_widget(_ORDER_STAGE_PREFIX, stage["uuid"])
            if name is not None: stage["name"] = name
        
        # Global Markers
        self._sync_marker_list(self.data["global_markers"], "global")

        # Feature Mappings
        for fm in self.data["feature_mappings"]:
            uid = fm["uuid"]
            name = self.get_node_widget(_FEATURE_MAPPING_NAME_PREFIX, uid)
            mode = self.get_node_widget(_FEATURE_MAPPING_MODE_PREFIX, uid)
            val = self.get_node_widget(_FEATURE_MAPPING_VALUE_PREFIX, uid)
            if name is not None: fm["feature_name"] = name
            if mode is not None: fm["mode"] = mode
            if val is not None: fm["value"] = val
        
        # Contingent refs
        for cm in self.data["contingent_markers"]:
            ref = st.session_state.get(self.get_widget_key(_CONTINGENT_REF_PREFIX, cm["uuid"]))
            if ref is not None: cm["ref"] = ref

        # LF Filters
        for lf in self.data["lexical_feature_filters"]:
            uid = lf["uuid"]
            name = self.get_node_widget(_LF_FILTER_NAME_PREFIX, uid)
            val = self.get_node_widget(_LF_FILTER_VAL_PREFIX, uid)
            if name is not None: lf["feature_name"] = name
            if val is not None: lf["feature_value"] = val

    def _sync_marker_list(self, markers: list[Marker], scope: str) -> None:
        """Helper to sync a list of Marker objects from widgets."""
        for marker in markers:
            m_uid = marker.uuid
            m_type = self.get_node_widget(_MARKER_TYPE_PREFIX, scope, suffix=m_uid)
            m_order = self.get_node_widget(_MARKER_ORDER_PREFIX, scope, suffix=m_uid)

            if m_type is not None:
                marker.type = m_type
            if m_order is not None:
                marker.order = m_order if m_order.strip() else None

            if marker.type == "replace":
                r_in = self.get_node_widget(_MARKER_REPLACE_IN_PREFIX, scope, suffix=m_uid)
                r_out = self.get_node_widget(_MARKER_REPLACE_OUT_PREFIX, scope, suffix=m_uid)
                if r_in is not None and r_out is not None:
                    marker.value = (r_in, r_out)
            else:
                val = self.get_node_widget(_MARKER_VALUE_PREFIX, scope, suffix=m_uid)
                if val is not None:
                    marker.value = val

    def to_yaml(self) -> dict:
        def serialize_markers(markers: list[Marker]) -> list[dict] | None:
            if not markers: return None
            res = []
            for m in markers:
                d = {"type": m.type, "value": m.value}
                if m.order: d["order"] = m.order
                res.append(d)
            return res

        fm_dict = {}
        for fm in self.data["feature_mappings"]:
            if not fm["feature_name"]: continue
            if fm["mode"] == "null": fm_dict[fm["feature_name"]] = None
            else: fm_dict[fm["feature_name"]] = fm["value"]

        lf_list = [[lf["feature_name"], lf["feature_value"]] for lf in self.data["lexical_feature_filters"] if lf["feature_name"]]

        doc = {
            "kind": self.kind,
            "part_of_speech": self.data["part_of_speech"],
            "order": [s["name"] for s in self.data["order_stages"] if s["name"]],
            "feature_markers": fm_dict,
            "feature_value_combinations": self.data["feature_value_combinations"] if self.data["feature_value_combinations"] else None,
            "contingent_markers": [cm["ref"] for cm in self.data["contingent_markers"] if cm["ref"]],
            "filter": {
                "pattern": self.data["pattern_filter"] if self.data["pattern_filter"] else None,
                "lexical_features": lf_list
            }
        }
        
        gm = serialize_markers(self.data["global_markers"])
        if gm: doc["global_markers"] = gm
        
        return doc

    def add_marker(self, markers: list[Marker]) -> None:
        markers.append(Marker(value="", type="suffix"))

    def remove_marker(self, markers: list[Marker], m_uuid: str) -> None:
        markers[:] = [m for m in markers if m.uuid != m_uuid]

    def insert_order_stage(self) -> None:
        self.data["order_stages"].append({"uuid": str(uuid.uuid4()), "name": ""})

    def remove_order_stage(self, uid: str) -> None:
        self.data["order_stages"] = [s for s in self.data["order_stages"] if s["uuid"] != uid]

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
        self.data["feature_mappings"].append({"uuid": str(uuid.uuid4()), "feature_name": "", "mode": "ref", "value": ""})

    def remove_feature_mapping(self, uid: str) -> None:
        self.data["feature_mappings"] = [f for f in self.data["feature_mappings"] if f["uuid"] != uid]

    def insert_contingent_ref(self) -> None:
        self.data["contingent_markers"].append({"uuid": str(uuid.uuid4()), "ref": ""})

    def remove_contingent_ref(self, uid: str) -> None:
        self.data["contingent_markers"] = [c for c in self.data["contingent_markers"] if c["uuid"] != uid]

    def insert_lf_filter(self) -> None:
        self.data["lexical_feature_filters"].append({"uuid": str(uuid.uuid4()), "feature_name": "", "feature_value": ""})

    def remove_lf_filter(self, uid: str) -> None:
        self.data["lexical_feature_filters"] = [lf for lf in self.data["lexical_feature_filters"] if lf["uuid"] != uid]


def paradigm_toolbar(editor: ParadigmEditor) -> None:
    col_save, col_preview_toggle, _ = st.columns([1.2, 1.6, 6])

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
        with st.container(border=True):
            st.caption("YAML preview — reflects unsaved edits")
            st.code(yaml.dump(editor.to_yaml(), allow_unicode=True, sort_keys=False))


def paradigm_page() -> None:
    st.set_page_config(page_title="Paradigm Editor", page_icon="🏗️", layout="wide")

    config_dir: str = st.session_state["config_dir"]
    config_walker: ConfigWalker = st.session_state["config_walker"]
    p_files = config_walker.config_filemap[_config_key]

    editor_sidebar(_config_kind, ParadigmEditor, config_dir, config_walker, p_files, _help_str)
    editor = editor_guard(kind=_config_kind)
    editor.read_form_to_state()
    editor_header(kind=_config_kind, editor=editor)

    grammar = st.session_state.get("grammar")
    available_pos = []
    available_features = []
    available_rules = []
    available_principal_parts = []
    available_fm = []
    available_cm = []
    available_combos = []
    available_patterns = []

    if grammar:
        available_pos = list(grammar.lexicon_registry.data.keys())
        available_features = list(grammar.feature_orchestrator.feature_values_registry.features_to_values.keys())
        available_rules = list(grammar.fst_orchestrator.rule_registry.data.keys())
        pp_sets = set()
        for pos_config in grammar.lexicon_registry.config_objects.values():
            for col in pos_config.get("columns", []): pp_sets.add(col)
        available_principal_parts = sorted(list(pp_sets))
        available_fm = sorted([Path(f).stem for f in config_walker.config_filemap["feature_marker_configs"]])
        available_cm = sorted([Path(f).stem for f in config_walker.config_filemap["contingent_feature_marker_configs"]])
        available_combos = sorted([Path(f).stem for f in config_walker.config_filemap["feature_combination_configs"]])
        available_patterns = sorted(list(grammar.fst_orchestrator.pattern_registry.data.keys()))

    # 1. Basics & Configuration
    with st.expander("Configuration", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.selectbox("Part of Speech", options=[""] + available_pos,
                         index=available_pos.index(editor.data["part_of_speech"]) + 1 if editor.data["part_of_speech"] in available_pos else 0,
                         key=editor.get_widget_key(_POS_PREFIX, "main"))
        with c2:
            st.selectbox("Feature Combinations", options=[""] + available_combos,
                         index=available_combos.index(editor.data["feature_value_combinations"].lstrip("$")) + 1 if editor.data["feature_value_combinations"].lstrip("$") in available_combos else 0,
                         key=editor.get_widget_key(_COMBO_REF_PREFIX, "main"),
                         format_func=lambda x: f"${x}" if x else "")
        with c3:
            st.selectbox("Pattern Filter", options=[""] + available_patterns,
                         index=available_patterns.index(editor.data["pattern_filter"]) + 1 if editor.data["pattern_filter"] in available_patterns else 0,
                         key=editor.get_widget_key(_PATTERN_FILTER_PREFIX, "main"))

    # 2. Order Stages
    with st.expander("Order Stages"):
        st.caption("Ordered stages of application. Markers should reference these.")
        for i, stage in enumerate(editor.data["order_stages"]):
            sc1, sc2, sc3, sc4 = st.columns([5, 0.5, 0.5, 0.5])
            with sc1:
                st.text_input("Stage name", value=stage["name"], key=editor.get_widget_key(_ORDER_STAGE_PREFIX, stage["uuid"]), label_visibility="collapsed")
            with sc2:
                if st.button("↑", key=f"up-{stage['uuid']}", disabled=(i == 0), help="Move up"):
                    editor.move_order_stage(stage["uuid"], "up")
                    st.rerun()
            with sc3:
                if st.button("↓", key=f"down-{stage['uuid']}", disabled=(i == len(editor.data["order_stages"]) - 1), help="Move down"):
                    editor.move_order_stage(stage["uuid"], "down")
                    st.rerun()
            with sc4:
                if st.button("✕", key=f"del-stage-{stage['uuid']}", help="Remove stage"):
                    editor.remove_order_stage(stage["uuid"])
                    st.rerun()
        if st.button("➕ Add order stage"):
            editor.insert_order_stage()
            st.rerun()

    # 3. Global Markers
    with st.expander("Global Markers"):
        render_marker_list(editor.data["global_markers"], "global", editor, available_rules, available_principal_parts, label="")

    # 4. Feature Mappings
    with st.expander("Feature Mappings", expanded=True):
        st.caption("Map features to specific marker sets or fixed values.")
        for fm in editor.data["feature_mappings"]:
            uid = fm["uuid"]
            with st.container(border=True):
                mc1, mc2, mc3, mc4 = st.columns([2, 1.5, 3, 0.4])
                with mc1:
                    st.selectbox("Feature", options=[""] + available_features,
                                 index=available_features.index(fm["feature_name"]) + 1 if fm["feature_name"] in available_features else 0,
                                 key=editor.get_widget_key(_FEATURE_MAPPING_NAME_PREFIX, uid))
                with mc2:
                    mode = st.selectbox("Source", options=["ref", "fixed", "null"],
                                        index=["ref", "fixed", "null"].index(fm["mode"]),
                                        format_func=lambda x: {"ref": "Marker Set", "fixed": "Fixed Value", "null": "Contingent Only"}[x],
                                        key=editor.get_widget_key(_FEATURE_MAPPING_MODE_PREFIX, uid))
                with mc3:
                    if mode == "ref":
                        st.selectbox("Value", options=[""] + available_fm,
                                     index=available_fm.index(fm["value"].lstrip("$")) + 1 if fm["value"].lstrip("$") in available_fm else 0,
                                     key=editor.get_widget_key(_FEATURE_MAPPING_VALUE_PREFIX, uid),
                                     format_func=lambda x: f"${x}" if x else "")
                    elif mode == "fixed":
                        st.text_input("Value", value=fm["value"], key=editor.get_widget_key(_FEATURE_MAPPING_VALUE_PREFIX, uid))
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
                st.selectbox("Ref", options=[""] + available_cm,
                             index=available_cm.index(cm["ref"].lstrip("$")) + 1 if cm["ref"].lstrip("$") in available_cm else 0,
                             key=editor.get_widget_key(_CONTINGENT_REF_PREFIX, cm["uuid"]),
                             format_func=lambda x: f"${x}" if x else "",
                             label_visibility="collapsed")
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
                st.selectbox("Lexical Feature", options=[""] + available_features,
                             index=available_features.index(lf["feature_name"]) + 1 if lf["feature_name"] in available_features else 0,
                             key=editor.get_widget_key(_LF_FILTER_NAME_PREFIX, uid),
                             label_visibility="collapsed")
            with lc2:
                # get values for selected feature
                l_vals = grammar.feature_orchestrator.feature_values_registry.features_to_values.get(lf["feature_name"], []) if grammar else []
                st.selectbox("Value", options=[""] + l_vals,
                             index=l_vals.index(lf["feature_value"]) + 1 if lf["feature_value"] in l_vals else 0,
                             key=editor.get_widget_key(_LF_FILTER_VAL_PREFIX, uid),
                             label_visibility="collapsed")
            with lc3:
                if st.button("✕", key=f"del-lf-{uid}"):
                    editor.remove_lf_filter(uid)
                    st.rerun()
        if st.button("➕ Add lexical filter"):
            editor.insert_lf_filter()
            st.rerun()

    toolbar_placeholder = st.empty()
    with toolbar_placeholder.container():
        paradigm_toolbar(editor)


if __name__ == "__main__":
    paradigm_page()
