import streamlit as st
from src.config_utils.watcher import start_watcher
from src.config_utils.config_walker import get_config_dir, ConfigWalker
from src.grammar import Grammar
from loguru import logger

from src.pages.inventory import inventory_page

GRAMMAR_REGISTRY_CACHE: dict[str, tuple[float, Grammar]] = {}
GRAMMAR_BUILD_STATUS: dict[tuple[str, str], dict] = {}


def load_grammar(config_walker: ConfigWalker) -> Grammar:
    config_data = config_walker.config_data
    grammar = Grammar(**config_data)
    return grammar


def initialize_state():
    """
    Loads directory watcher and GrammarRegistry.
    """

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
        watcher = start_watcher(
            config_dir=config_dir, invalidate_keys=["grammar", "config_walker"]
        )
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
