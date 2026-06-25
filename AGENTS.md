# GEMINI.md - Project Context & Instructions

## Project Overview

The **Tira Parser** (`tira-parser`) is a morphological analyzer, decomposer, and inflector for the Tira language. It uses Finite-State Transducer (FST) technology, primarily leveraging the **Pynini** (Python wrapper for OpenFST) library. The project is designed to be highly configuration-driven, where morphological rules, paradigms, and lexicons are defined in YAML files and compiled into FSTs.

### Core Technologies

- **Python 3.8+**
- **Pynini (OpenFST):** Core FST engine for morphological rules and transformations.
- **Streamlit:** Provides a web-based "Grammar Workbench" for editing and visualizing the grammar.
- **YAML:** Used for all grammar configurations (lexicon, rules, paradigms, etc.).
- **JSON Schema:** Used to validate grammar configurations.
- **Pandas:** Used for handling lexicon data and test cases.

### Key Architectural Concepts

- **Registries:** Specialized classes (e.g., `InventoryRegistry`, `LexiconRegistry`, `ParadigmRegistry`) that load specific types of YAML configs and interpret them into logic or FSTs.
- **Orchestrators:** High-level classes (e.g., `Grammar`, `FstOrchestrator`) that coordinate multiple registries to provide a unified interface for parsing and inflection.
- **Config-Driven Logic:** Most grammar behavior is defined in `config/tira/` and validated against schemas in `config/schemas/`.

## Directory Structure

- `src/`: Main source code.
  - `src/grammar/`: Core logic, orchestrators, and registries.
  - `src/pages/`: Streamlit UI components for the Grammar Workbench.
  - `src/config_utils/`: Utilities for loading and validating configurations.
  - `src/search/`: FST-based search logic.
- `config/`: Configuration files.
  - `config/tira/`: The active Tira grammar configuration.
  - `config/example/`: Minimal examples for testing.
  - `config/schemas/`: JSON schemas for validating YAML configs.
- `tests/`: Unit and integration tests using `pytest`.
- `scripts/`: Utility scripts for data generation, migration, and scraping.
- `.plans/`: Design documents and project plans.
- `deprecated/`: Reference-only legacy code.

## Development Workflows

### Environment Setup

1. **Activate Environment:**

   ```bash
   source .venv/bin/activate
   ```

2. **Install Dependencies:**

   ```bash
   pip install -e .
   ```

   *Note: Requires OpenFST to be installed on the system for Pynini.*

### Running the Grammar Workbench (Streamlit)

To start the web UI for grammar development:

```bash
CONFIG_DIR=./config streamlit run src/app.py
```

You can point `CONFIG_DIR` to `config/tira` to load the full grammar.

### Testing

Run all tests using `pytest`:

```bash
pytest
```

Tests are located in the `tests/` directory and follow the `*_test.py` naming convention.

### Adding or Modifying Grammar

1. **Edit YAMLs:** Modify files in `config/tira/` (e.g., `paradigm/`, `rules/`, `lexicon/`).
2. **Validate:** Ensure edits follow the schemas in `config/schemas/`.
3. **Verify:** Use the Streamlit workbench or run tests to verify the changes.

## Development Conventions

### Coding Style

- **Indentation:** 4 spaces.
- **Naming:** `snake_case` for functions and variables, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants.
- **Type Hints:** Required for all new or modified code.
- **Modularization:** Keep UI logic (`src/pages/`) strictly separate from parsing and registry logic (`src/grammar/`).

### Testing Practices

- Prefer narrow unit tests for registries and orchestrators.
- Use `config/example/` for test fixtures when possible.
- Regression tests should use data from `data/test_cases/`.

### Configuration Tips

- `CONFIG_DIR` is the primary environment variable controlling which grammar is loaded.
- `src/config_utils/config_walker.py` handles the recursive loading and validation of YAML trees.
- Avoid editing `config/tira/` directly for experimental changes; use a separate config root or add to `config/example/`.

## Key Files to Watch

- `src/grammar/orchestrator/grammar_orchestrator.py`: The main entry point for the grammar logic.
- `src/grammar/orchestrator/fst_orchestrator.py`: Core FST compilation logic.
- `src/app.py`: Main entry point for the Streamlit application.
- `pyproject.toml`: Dependency and metadata management.
- `AGENTS.md`: Specific guidelines for AI agents interacting with this repo.
