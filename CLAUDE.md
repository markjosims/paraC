# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Tool for building morphological parsers for language documentation. Currently focused on Tira (an under-studied language). Uses finite-state transducers (FSTs) via `pynini` for morphological parsing and inflection.

## Commands

```bash
# Install (editable, with dev deps)
pip install -e ".[dev]"

# Run Streamlit UI
CONFIG_DIR=config/example streamlit run src/streamlit/app.py

# Run Flask UI (legacy)
python app.py --config_dir config/example

# Run tests
pytest

# Run a single test
pytest tests/grammar_registry_test.py::test_paradigm_markers_combine_global_standard_and_contingent_markers_for_ipfv_slots

# Validate YAML configs against JSON schemas
python -m src.config_utils.schema_validation

# CLI
python -m src.cli inflect_word ap --tam imperfective --deixis itive --class r
python -m src.cli parse_word "rá ápà"
python -m src.cli search_word "àprìɲ"
python -m src.cli search_corpus apri
```

## Architecture

The codebase has two layers: the **grammar backend** (`src/grammar/`) and the **web frontend** (being migrated from Flask `src/web/` to Streamlit `src/streamlit/`).

### Grammar backend (`src/grammar/`)

Initialization is split into two phases: *reading* (YAML → dicts, handled by `Grammar.from_config_dir` via `ConfigWalker`) and *loading* (dicts → actionable objects like FSTs).

The class hierarchy, from bottom to top:
- **`Registry`** (`src/grammar/classes.py`) — base class; loads a single config kind from YAML dicts
- **`Orchestrator`** — base class; sits over a group of Registries and manages cross-registry concerns
- **`FstOrchestrator`** (`src/grammar/orchestrator/fst_orchestrator.py`) — orchestrates `InventoryRegistry`, `PatternRegistry`, `RuleRegistry`; compiles FSTs in 8 sequential stages; exposes FST compilation helpers for other classes
- **`FeatureOrchestrator`** (`src/grammar/orchestrator/feature_orchestrator.py`) — orchestrates `FeatureValuesRegistry` and `FeatureCombinationRegistry`
- **`MarkerOrchestrator`** (`src/grammar/orchestrator/marker_orchestrator.py`) — orchestrates `FeatureMarkerRegistry` and `ContingentMarkerRegistry`
- **`Grammar`** (`src/grammar/orchestrator/grammar_orchestrator.py`) — top-level class; wires all orchestrators together; imported as `from src.grammar import Grammar`

The `Paradigm` class (`src/grammar/paradigm.py`) is the primary consumer of `Grammar`; it combines `FeatureValueCombinations` + markers + FSTs to expose `get_inflection_stages()`, `get_subparadigm_table()`, `get_parses()`, and `search_form()`.

### Config system (`src/config_utils/`)

YAML configs live under `config/` and each has a `kind` field (one of `CONFIG_KINDS` in `schema_validation.py`). `ConfigWalker` globs all YAMLs in a directory, validates them against JSON schemas in `config/schemas/`, and resolves `$name` cross-file references. `src/constants.py` defines `EXAMPLE_CONFIG_DIR` and `TIRA_CONFIG_DIR`.

### Streamlit frontend (`src/streamlit/`) — in progress

- `src/streamlit/app.py` — entry point; sets up navigation and initializes state
- `src/streamlit/state/` — session state helpers (`config_paths.py`, `registry_loader.py`)
- `src/streamlit/pages/` — one file per page (inventory, patterns, inflector, parser, corpus)

State is managed via `st.session_state`. A file watcher (`src/config_utils/watcher.py`) monitors the config directory and invalidates the cached `Grammar` on YAML changes.

### Flask frontend (`src/web/`) — legacy, being replaced

Each editor kind has a Python state manager (`InventoryEditor`, `PatternEditor`, etc.) that serializes state to/from YAML and JSON. `src/web/routes.py` is the Flask blueprint with 48 routes. The editor pattern: state is serialized as JSON into a hidden form field, submitted via `fetch`, and the server returns updated HTML fragments for DOM replacement.

### Key note on `src/registry/` vs `src/grammar/`

Tests and some Streamlit state helpers still import from `src.registry.*` (the old module path). The canonical location is `src.grammar.*`. This inconsistency is in-progress cleanup.
