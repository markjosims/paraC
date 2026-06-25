# Tira Morphological Parser (tira-parser)

Morphological parser and inflector for the Tira language using Finite-State Transducer (FST) technology. It is designed to handle complex morphological processes such as tonal exponence and fuzzy matching.

## Project Overview

*   **Purpose:** Provide a robust tool for morphological decomposition, analysis, and generation of Tira text.
*   **Core Technology:**
    *   **Python:** Primary development language.
    *   **Pynini:** Python wrapper for OpenFST, used for context-dependent rewrite rules and paradigm management.
    *   **Numba:** Used for JIT-accelerated beam search for performance-optimized parsing.
    *   **Streamlit:** Provides a web-based UI for editing configurations and testing the parser/inflector.
    *   **Pandas:** Data manipulation for lexicons and results.
*   **Architecture:**
    *   **Orchestration:** The `Grammar` class (`src/grammar/orchestrator/grammar_orchestrator.py`) is the top-level object that integrates various registries (lexicon, paradigm, morpheme sequence, etc.).
    *   **FST Engine:** `FstOrchestrator` (`src/grammar/orchestrator/fst_orchestrator.py`) compiles user-defined inventory, patterns, and rules into FSTs.
    *   **Search Engine:** Implements a performance-optimized beam search (`src/search/beam_search.py`) using Compressed Sparse Row (CSR) representations of WFSAs and Numba JIT.
    *   **UI:** A multi-page Streamlit application (`src/app.py`) for interactive development and testing.

## Building and Running

### Prerequisites
*   **Linux/macOS:** Python 3.8+, OpenFST 1.8.3 (for Pynini).
*   **Windows:** Use WSL.

### Installation
```bash
pip install -r requirements.txt
```

### Running the UI
The Streamlit app is the primary interface for interactive work:
```bash
streamlit run src/app.py
```

### Command Line Interface (CLI)
*   **Command:** `tira` (defined in `pyproject.toml`) or `python -m src.cli`
*   **Status Note:** `src/cli.py` is mentioned in `README.md` and `pyproject.toml` but was missing during initial analysis. Verify existence before use.
*   **Functions:** `inflect_word`, `parse_word`, `search_word`, `get_gloss_for_root`, `search_corpus`.

### Testing
Use `pytest` to run the test suite:
```bash
pytest
```
Tests are located in the `tests/` directory and primarily use the `config/example` configuration for fast validation.

## Development Conventions

*   **Logging:** Uses `loguru`. Prefer `logger.info`, `logger.success`, `logger.warning`, and `logger.error` over `print`.
*   **Configuration:** 
    *   YAML files are used for defining linguistic data (inventory, rules, patterns).
    *   JSON schemas (`config/schemas/`) are used to validate configuration files.
    *   `RecursiveNamespace` is often used to wrap configuration dictionaries.
*   **Performance:** Performance-critical search code is JIT-optimized with Numba (`src/search/beam_search_jit.py`). Avoid adding Python-level overhead in these sections.
*   **State Management:** In the Streamlit app, a `watcher` (`src/config_utils/watcher.py`) monitors configuration files and invalidates the session state to trigger reloads when changes are detected.

## Key Directories

*   `src/`: Core source code.
    *   `grammar/`: FST orchestration and linguistic registries.
    *   `search/`: Beam search and edit modeling logic.
    *   `config_utils/`: Configuration loading, validation, and file watching.
    *   `pages/`, `widgets/`: Streamlit UI components.
*   `config/`:
    *   `tira/`: Production linguistic data.
    *   `example/`: Minimal data for testing and examples.
    *   `schemas/`: JSON schemas for configuration validation.
*   `data/`: Lexicons, test cases, and corpus data (CSV, XLSX, TXT).
*   `scripts/`: Utility scripts for building lexicons and datasets.
*   `plans/`: Design documents and future development plans.
