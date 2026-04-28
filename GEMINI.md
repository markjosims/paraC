# Gemini CLI Project Context: Tira Parser

This project is a morphological parser and inflector for the Tira language, built using Finite State Transducers (FSTs) via the [Pynini](https://pynini.openfst.org/) library.

## Project Overview

*   **Goal:** Provide a robust system for morphological analysis (parsing) and synthesis (inflection) of Tira, accounting for complex processes like tonal exponence and long-distance dependencies.
*   **Technologies:** Python, Pynini (OpenFST), Streamlit (UI), Pandas, Loguru (Logging), PyYAML.
*   **Key Architecture:** The project uses a **Registry and Orchestrator pattern**. Grammar components (Inventory, Patterns, Rules, Paradigms, Lexicons) are managed by specialized registries, which are coordinated by orchestrators. The `Grammar` class (`src/grammar/orchestrator/grammar_orchestrator.py`) is the top-level entry point for the language grammar.

## Building and Running

### Prerequisites
*   **OpenFST:** Required by Pynini. On Linux, `pip install` usually handles it. On macOS/Windows, it must be installed manually (see `README.md` for specific instructions).

### Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Install project in editable mode
pip install -e .
```

### Running the Web UI
The project includes a Streamlit-based interface for editing and testing the grammar.
```bash
streamlit run src/app.py
```

### Running Tests
```bash
pytest
```

### CLI
The project structure has recently been refactored. The legacy CLI (`deprecated/cli.py`) is no longer compatible with the new registry-based architecture. A new CLI is intended to be implemented (referenced as `tira` in `pyproject.toml`), but currently, the primary interface is the Streamlit app.

## Project Structure

*   `src/grammar/`: Core logic for the morphological system.
    *   `registry/`: Specialized handlers for different grammar components (e.g., `paradigm_registry.py`, `rule_registry.py`).
    *   `orchestrator/`: Classes that coordinate multiple registries (e.g., `fst_orchestrator.py`, `grammar_orchestrator.py`).
*   `src/config_utils/`: Utilities for loading and validating configuration files.
*   `src/pages/`: Streamlit UI page definitions.
*   `config/`: Configuration files (YAML/JSON) that define the Tira grammar.
    *   `tira/`: The active Tira grammar configuration.
    *   `example/`: Smaller grammar used for testing.
    *   `schemas/`: JSON schemas used for configuration validation.
*   `data/`: Raw and processed data (lexicons, test cases, ELAN exports).
*   `tests/`: Unit and integration tests for the registry system and FST logic.

## Development Conventions

*   **Configuration-Driven:** Most grammar changes should be made by modifying files in `config/tira/` rather than code.
*   **Logging:** Use `loguru` for logging. The log level can be adjusted via the `TIRA_LOG_LEVEL` environment variable (defaults to `INFO`).
*   **Registry Pattern:** When adding new grammar features, ensure they are registered within the appropriate registry and exposed via the `Grammar` orchestrator.
*   **Validation:** All configuration files should adhere to the schemas defined in `config/schemas/`. Use `src/config_utils/schema_validation.py` to verify configurations.
