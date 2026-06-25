"""
Streamlit Inflector Page
========================
A UI for testing inflection and viewing intermediate stages for Paradigms
and MorphemeSequences.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
from src.grammar import Grammar
from src.grammar.registry.paradigm_registry import Paradigm
from src.grammar.registry.morpheme_sequence_registry import MorphemeSequence
from src.grammar.registry.feature_values_registry import Feature


def inflector_page() -> None:
    st.set_page_config(page_title="Inflector", page_icon="🧪", layout="wide")
    st.title("🧪 Inflector")
    st.caption(
        "Test inflection and view intermediate stages for Paradigms or MorphemeSequences."
    )

    grammar: Grammar = st.session_state.get("grammar")
    if not grammar:
        st.error("Grammar not loaded. Please ensure your configuration is valid.")
        return

    # 1. Selection
    inflect_type = st.radio(
        "Inflection Type", ["Paradigm", "MorphemeSequence"], horizontal=True
    )

    available_items = []
    if inflect_type == "Paradigm":
        available_items = sorted(list(grammar.paradigm_registry.data.keys()))
    else:
        available_items = sorted(list(grammar.morpheme_sequence_registry.data.keys()))

    if not available_items:
        st.warning(f"No {inflect_type}s found in configuration.")
        return

    selected_name = st.selectbox(f"Select {inflect_type}", available_items)

    if not selected_name:
        return

    st.divider()

    lexical_features = {}

    # 2. Setup Inputs based on selection
    if inflect_type == "Paradigm":
        obj: Paradigm = grammar.paradigm_registry.get_paradigm(selected_name)
        if not obj.is_initialized:
            obj.initialize()

        st.subheader(f"Paradigm: {selected_name}")

        # Stem Input
        use_lexicon = st.checkbox("Use lexicon for stem", value=True)
        stem = ""
        if use_lexicon:
            roots = obj.lexicon.get_roots()
            stem = st.selectbox("Select Root", roots)
        else:
            stem = st.text_input("Enter Stem", placeholder="e.g. po")

        # Features
        st.write("#### Feature Values")
        fixed: dict[str, Feature] = obj.fixed_features or {}

        # Get free features

        free_features: list[Feature] = [
            feature for feature in obj.features if feature.name not in fixed
        ]

        feature_values = fixed.copy()
        if free_features:
            cols = st.columns(3)
            for i, feature in enumerate(free_features):
                f_name = feature.name
                f_vals = feature.values
                with cols[i % 3]:
                    val = st.selectbox(
                        f_name, [""] + sorted(f_vals), key=f"feat-{f_name}"
                    )
                    if val:
                        feature_values[f_name] = val

        if st.button("Run Inflection", type="primary"):
            if not stem:
                st.error("Please provide a stem.")
            else:
                try:
                    stages = obj.get_inflection_stages(stem, feature_values)
                    _render_stages_table(stages)
                except Exception as e:
                    st.error(f"Error: {e}")

    else:  # MorphemeSequence
        obj: MorphemeSequence = grammar.morpheme_sequence_registry.get_sequence(
            selected_name
        )
        if not obj.is_initialized:
            obj.initialize()

        st.subheader(f"MorphemeSequence: {selected_name}")

        # Determine steps that need stems
        stem_steps = []
        for i, (item, resolved) in enumerate(zip(obj.sequence_data, obj.morphemes)):
            if item["type"] in ["Lexicon", "Paradigm"]:
                stem_steps.append(
                    {
                        "index": i,
                        "type": item["type"],
                        "value": item["value"],
                        "resolved": resolved,
                    }
                )

        st.write("#### Stems")
        st.caption("One stem required for each Lexicon or Paradigm step.")
        st_use_lexicon = st.checkbox(
            "Use lexicon dropdowns where available", value=True
        )

        stems = []
        for i, step in enumerate(stem_steps):
            label = (
                f"Step {step['index'] + 1}: {step['type']}"
                + f"({step['resolved'].name if hasattr(step['resolved'], 'name') else step['resolved']})"
            )
            if st_use_lexicon:
                if step["type"] == "Lexicon":
                    roots = step["resolved"].get_roots()
                    s = st.selectbox(label, roots, key=f"ms-stem-{i}")
                    lexical_features.update(step["resolved"].get_features_for_root(s))
                    stems.append(s)
                elif step["type"] == "Paradigm":
                    roots = step["resolved"].lexicon.get_roots()
                    s = st.selectbox(label, roots, key=f"ms-stem-{i}")
                    lexical_features.update(
                        step["resolved"].lexicon.get_features_for_root(s)
                    )
                    stems.append(s)
            else:
                s = st.text_input(label, key=f"ms-stem-{i}")
                stems.append(s)

        # Features
        st.write("#### Feature Values")
        all_features = sorted(list(obj.features))

        feature_values = obj.fixed_features.copy()
        if all_features:
            cols = st.columns(3)
            for i, feature in enumerate(all_features):
                if feature.name in obj.fixed_features:
                    continue

                if feature.name in lexical_features:
                    feature_values[feature.name] = lexical_features[feature.name]
                    st.write(
                        f"{feature.name}: {lexical_features[feature.name]} (from lexicon)"
                    )
                    continue

                with cols[i % 3]:
                    val: str = st.selectbox(
                        feature.name,
                        options=feature.values,
                        key=f"ms-feat-{feature.name}",
                    )
                    if val:
                        feature_values[feature.name] = val

        if st.button("Run Inflection", type="primary"):
            if any(not s for s in stems):
                st.error("Please provide all stems.")
            else:
                try:
                    stages = obj.get_inflection_stages(stems, feature_values)
                    _render_stages_table(stages)
                except Exception as e:
                    st.error(f"Error: {e}")


def _render_stages_table(stages: list[dict]):
    if not stages:
        st.warning("No stages returned.")
        return

    st.write("### Inflection Stages")
    df = pd.DataFrame(stages)
    # Clean up for display
    if "fst" in df.columns:
        df = df.drop(columns=["fst"])

    # Format Paradigm stages if present (they have different columns)
    # Actually Paradigm.get_inflection_stages and MorphemeSequence.get_inflection_stages
    # might return slightly different shapes.

    st.table(df)


if __name__ == "__main__":
    inflector_page()
