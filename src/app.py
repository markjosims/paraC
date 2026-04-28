import streamlit as st
from src.config_utils.watcher import start_watcher, check_and_apply_invalidation
from src.config_utils.config_walker import get_config_dir, ConfigWalker
from src.grammar import Grammar
from loguru import logger

from src.pages.inventory import inventory_page
from src.pages.feature_values import feature_values_page
from src.pages.feature_combinations import feature_combinations_page
from src.pages.feature_markers import feature_markers_page
from src.pages.contingent_markers import contingent_markers_page
from src.pages.lexicon import lexicon_page
from src.pages.paradigm import paradigm_page
from src.pages.patterns import patterns_page
from src.pages.rules import rules_page

_INVALIDATE_KEYS = ["grammar", "config_walker"]


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
        "Edit grammar": [
            st.Page(inventory_page, title="Inventory"),
            st.Page(feature_values_page, title="Feature Values"),
            st.Page(feature_combinations_page, title="Feature Combinations"),
            st.Page(feature_markers_page, title="Feature Markers"),
            st.Page(contingent_markers_page, title="Contingent Markers"),
            st.Page(lexicon_page, title="Lexicon"),
            st.Page(paradigm_page, title="Paradigm"),
            st.Page(patterns_page, title="Patterns"),
            st.Page(rules_page, title="Rules"),
        ],
        "Inflect": [],
        "Parse": [],
        "Corpus": [],
    }
    return st.navigation(pages, position="top")


def home_page():
    st.header("Home page")


def main():
    initialize_state()
    pages = navbar()
    pages.run()


if __name__ == "__main__":
    main()
