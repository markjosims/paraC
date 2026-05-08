from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
from src.config_utils.watcher import start_watcher, check_and_apply_invalidation
from src.config_utils.config_walker import get_config_dir, ConfigWalker
from src.config_utils.schema_validation import CONFIG_KINDS
from src.grammar import Grammar
from loguru import logger
from camel_converter import to_snake

from src.pages.inventory import inventory_page
from src.pages.feature_values import feature_values_page
from src.pages.feature_combinations import feature_combinations_page
from src.pages.feature_markers import feature_markers_page
from src.pages.contingent_markers import contingent_markers_page
from src.pages.lexicon import lexicon_page
from src.pages.paradigm import paradigm_page
from src.pages.morpheme_sequence import morpheme_sequence_page
from src.pages.morpheme_set import morpheme_set_page
from src.pages.patterns import patterns_page
from src.pages.rules import rules_page
from src.pages.inflector import inflector_page

_INVALIDATE_KEYS = ["grammar", "config_walker"]

_HOME_NAV_GROUPS = {
    "Phonology": ["Inventory", "Patterns", "Rules"],
    "Exponence": [
        "Feature Values",
        "Feature Combinations",
        "Morpheme Set",
        "Feature Markers",
        "Contingent Markers",
    ],
    "Morphotactics": ["Morpheme Sequence", "Paradigm"],
    "Lexicon": ["Lexical Roots"],
    "Inflect": ["Inflector"],
}


def _config_key_for_kind(kind: str) -> str:
    return f"{to_snake(kind).removesuffix('s')}_configs"


def _kind_label(kind: str) -> str:
    label = to_snake(kind).replace("_", " ").title()
    return label.replace(" Of ", " of ")


def _recent_config_files(config_walker: ConfigWalker, limit: int = 6) -> list[Path]:
    paths = [
        Path(path)
        for files in config_walker.config_filemap.values()
        for path in files
    ]

    def modified_time(path: Path) -> float:
        try:
            return path.stat().st_mtime
        except OSError:
            return 0

    paths.sort(key=modified_time, reverse=True)
    return paths[:limit]


def load_grammar(config_walker: ConfigWalker) -> Grammar:
    config_data = config_walker.config_data
    grammar = Grammar(**config_data)
    return grammar


def initialize_state():
    """
    Checks for config file changes, then ensures the watcher, config
    walker, and grammar are loaded into session state.
    """
    # Check watcher flag first — must run every rerun from the main thread.
    if check_and_apply_invalidation(_INVALIDATE_KEYS):
        logger.info("Config invalidation detected. Rerunning to reload config...")
        st.rerun()

    config_dir = st.session_state.get("config_dir", None)
    config_walker = st.session_state.get("config_walker", None)
    watcher = st.session_state.get("watcher", None)
    grammar = st.session_state.get("grammar", None)

    if config_dir is None:
        config_dir = get_config_dir()
        logger.info(f"Config dir set to {config_dir}")
        st.session_state["config_dir"] = config_dir
    if config_walker is None:
        logger.info("Making config walker...")
        config_walker = ConfigWalker(config_dir=config_dir)
        st.session_state["config_walker"] = config_walker
    if watcher is None:
        logger.info("Starting watcher...")
        watcher = start_watcher(config_dir=config_dir)
        st.session_state["watcher"] = watcher
    if grammar is None:
        logger.info(f"Loading grammar from {config_dir}...")
        grammar = load_grammar(config_walker=config_walker)
        st.session_state["grammar"] = grammar

def navbar():
    pages = {
        "Home": [st.Page(home_page, title="Home")],
        "Phonology": [
            st.Page(inventory_page, title="Inventory"),
            st.Page(patterns_page, title="Patterns"),
            st.Page(rules_page, title="Rules"),
        ],
        "Exponence": [
            st.Page(feature_values_page, title="Feature Values"),
            st.Page(feature_combinations_page, title="Feature Combinations"),
            st.Page(morpheme_set_page, title="Morpheme Set"),
            st.Page(feature_markers_page, title="Feature Markers"),
            st.Page(contingent_markers_page, title="Contingent Markers"),
        ],
        "Morphotactics": [
            st.Page(morpheme_sequence_page, title="Morpheme Sequence"),
            st.Page(paradigm_page, title="Paradigm"),
        ],
        "Lexicon": [
            st.Page(lexicon_page, title="Lexical Roots"),

        ],
        "Inflect": [
            st.Page(inflector_page, title="Inflector"),
        ],
        "Parse": [],
        "Corpus": [],
    }
    return st.navigation(pages, position="top")


def home_page():
    config_walker = st.session_state.get("config_walker")
    grammar = st.session_state.get("grammar")
    config_dir = st.session_state.get("config_dir", "")

    st.header("Tira Config Dashboard")

    if config_walker is None:
        st.error("Config walker not found in session state.")
        st.stop()

    total_files = sum(len(files) for files in config_walker.config_filemap.values())
    loaded_groups = sum(
        1 for files in config_walker.config_filemap.values() if len(files) > 0
    )
    grammar_status = (
        "Loaded"
        if grammar is not None and getattr(grammar, "is_initialized", False)
        else "Not loaded"
    )

    status_col, group_col, file_col = st.columns(3)
    status_col.metric("Grammar", grammar_status)
    group_col.metric("Config groups", f"{loaded_groups}/{len(CONFIG_KINDS)}")
    file_col.metric("YAML files", total_files)

    st.caption(f"`CONFIG_DIR`: `{config_dir}`")
    st.divider()

    count_rows = []
    for kind in CONFIG_KINDS:
        key = _config_key_for_kind(kind)
        files = config_walker.config_filemap.get(key, [])
        count_rows.append(
            {
                "Config type": _kind_label(kind),
                "Files": len(files),
            }
        )

    left_col, right_col = st.columns([2, 1.2])
    with left_col:
        st.subheader("Config Coverage")
        st.dataframe(count_rows, hide_index=True, use_container_width=True)

    with right_col:
        st.subheader("Recent Files")
        recent_files = _recent_config_files(config_walker)
        if not recent_files:
            st.info("No YAML files found.")
        else:
            for path in recent_files:
                try:
                    label = path.relative_to(config_walker.config_dir)
                except ValueError:
                    label = path
                st.markdown(f"`{label}`")

    st.subheader("Editor Areas")
    for group, pages in _HOME_NAV_GROUPS.items():
        with st.container(border=True):
            st.markdown(f"**{group}**")
            st.caption(", ".join(pages))


def main():
    initialize_state()
    pages = navbar()
    pages.run()


if __name__ == "__main__":
    main()
