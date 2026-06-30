# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

This is **parC**, a toolkit for building and applying morphological analyzers (finite-state-transducer-based parsers) from linguistic fieldwork data.

There is no committed git history yet (`main` has no commits); treat the working tree as the source of truth rather than `git log`/`git blame`.

## Commands

- Install deps: `uv sync` (or `pip install -e .`) — this is a `uv`-managed project (`uv.lock` present).
- Validate config YAML against JSON schemas: `python -m src.config_utils.schema_validation` (runs `validate_files_by_kind` for every `CONFIG_KINDS` entry against `config/` by default).
- Tests: there is no test suite in the repo currently (`pytest` is a declared dependency but no `test_*.py` files exist yet). When adding tests, `pytest` is already available via the project's dependencies.
- The `tira` CLI entry point is declared in `pyproject.toml` (`tira = "src.cli:main"`) but `src/cli.py` does not currently exist — don't assume it's runnable until it's (re)added.
- Required environment: a config directory must be available via `YAML_DIR` in `.env` (e.g. `YAML_DIR=config/tira` or `config/example`), since `ConfigWalker` reads from it on construction. `PARC_LOG_LEVEL`/`TIRA_LOG_OUTPUT` env vars control `loguru` logging (see `src/__init__.py`).

## Architecture

### Config-driven grammar model

The core domain model is built entirely from YAML config files (validated against JSON Schemas in `schemas//`) describing a language's grammar. A given language's configs live under `config/<language>/<kind_dir>/*.yaml` (e.g. `config/tira/`, `config/spanish/`, `config/example/`), with one subdirectory per **config kind**: `inventory`, `patterns`, `rules`, `feature_definitions`, `feature_combinations`, `morpheme_set`, `feature_markers`, `contingent_feature_markers` (dir named `contingent_marker`), `part_of_speech`, `morpheme_sequence`, `paradigm`.

- `src/config_utils/config_walker.py` (`ConfigWalker`) reads and validates all YAML for a config dir against schemas, normalizes kind names (PascalCase → `snake_case` + `_configs` suffix, e.g. `FeatureMarkers` → `feature_markers_configs`), and resolves `$name` cross-file references (a string starting with `$` is replaced by the referenced YAML file's content, resolved recursively).
- `src/config_utils/schema_validation.py` loads/validates JSON Schemas from `schemas//`, including resolving cross-schema `$ref`s into local definitions (custom resolver, not `jsonref`, to avoid recursion issues).
- `src/config_utils/watcher.py` watches the config directory for changes and triggers invalidation/reload of cached state.

### Reading vs. loading

Per `src/grammar/classes.py`, grammar construction happens in two stages:
1. **Reading** — `ConfigWalker` reads YAML into plain dicts. No interpretation.
2. **Loading** — `Orchestrator`/`Registry` subclasses interpret that data into actionable logic (e.g. inventory phones get compiled into `pynini` FSTs).

Two base classes anchor this:
- `Registry` (`src/grammar/classes.py`) holds all data for one config kind. Subclasses implement `load_all_configs()` and `load_data_from_config()`.
- `Orchestrator` sits above a group of `Registry` instances for one area of grammar (currently no shared logic — organizational only).

### Orchestrator/Registry tree

`src/grammar/orchestrator/grammar_orchestrator.py` defines `Grammar`, the top-level orchestrator-of-orchestrators, constructed from all `*_configs` dicts produced by `ConfigWalker`. It wires together (in dependency order):

- `FeatureOrchestrator` (`feature_orchestrator.py`) — morphological features and their values/combinations.
- `FstOrchestrator` (`fst_orchestrator.py`, the largest file in the codebase) — compiles phoneme inventory, patterns, and phonological rules into `pynini` FSTs; depends on `FeatureOrchestrator`.
- `LexiconRegistry` — parts of speech / lexical roots; depends on `FeatureOrchestrator` + `FstOrchestrator`.
- `MarkerOrchestrator` (`marker_orchestrator.py`) — feature markers and contingent feature markers (morphological exponence); depends on `FeatureOrchestrator`.
- `MorphemeSetRegistry` — sets of morphemes exponing feature combinations; depends on `FeatureOrchestrator` + `FstOrchestrator`.
- `ParadigmRegistry` (`paradigm_registry.py`, largest registry) — inflectional paradigms; depends on `MarkerOrchestrator`, `LexiconRegistry`, `FstOrchestrator`.
- `MorphemeSequenceRegistry` — morphotactic sequencing of morphemes within a word; depends on everything above. Its `initialize_sequences()` is deliberately called last, after all other registries exist (see `Grammar.initialize()`).

When extending the grammar model, follow this same dependency order — most registries take already-constructed orchestrators/registries as constructor args rather than reaching into global state.

### FST utilities and parsing/search

- `src/fst_utils.py` defines `ReservedSymbolMixin` (the fixed set of special symbols/operators used across pattern strings, rules, and morpheme definitions — e.g. `[BOW]`/`[EOW]` word-boundary tags, edit-operation tags `[INSERT]`/`[SUBSTITUTE]`/`[DELETE]`, boundary symbols `-`/`=`/`_`, and operators `*`, `+`, `?`, `|`, `^`, parens, braces) plus `Acceptor`/`Transducer`/`TransducerList`/`Prefix`/`Suffix` wrapper dataclasses around `pynini.Fst` objects. These wrappers enforce a "build once" discipline (`set_acceptor`/`set_transducer` raise/warn if called more than once or on the wrong FST type).
- `src/search/` implements fuzzy form search and parsing over the compiled FSTs: `beam_search.py` / `beam_search_jit.py` (numba-jitted variant) implement beam search for matching surface forms against the parser despite edits/errors; `edit_graph.py` and `edit_modeling.py` model edit operations for that search. `beam_search_jit_stale.py` is a stale/superseded variant — check before using.

### Pattern strings

Pattern strings (used in inventory classes, the Patterns module, morpheme definitions, and rule contexts) form a small regex-like DSL over phones/symbols using the operators captured in `ReservedSymbolMixin`: `<ClassName>` references an inventory class or named pattern, `|` is disjunction, `{A B}` is union/optionality of literal tokens, `*`/`+`/`?` are the usual closures, and `^` negates inside braces. See `doc/grammar_modules.rst` for the linguistic rationale (phonology vs. exponence vs. morphotactics module split) — this doc is the closest thing to a design doc and is useful background before changing the schemas in `schemas//`.

### Constants

`src/constants.py` defines path constants (`PROJECT_ROOT`, `CONFIG_ROOT`, `EXAMPLE_YAML_DIR`, `TIRA_YAML_DIR`, `SCHEMA_DIR`) and two `pynini`-specific symbol-table indices (`BOS_INDEX`, `EOS_INDEX`) copied from upstream `pynini` source — don't change these without checking `pynini`'s `stringcompile.h`.

### Planned: JSON Config Editor (PoC)

`plans/jsoneditor.md` specifies a not-yet-built browser-based editor for the typed JSON/YAML config files (replacement for the deprecated Streamlit UI). Read that file in full before implementing any part of it. Key points:

- **Stack:** vanilla JS ES modules (no build step), `vanilla-jsoneditor` + bundled AJV via CDN on the frontend; a FastAPI backend exposing 4 endpoints: `GET /schemas/{kind}`, `GET /configs?type={Type}`, `GET /file?path=`, `PUT /file?path=`. `/configs` returns `$`-prefixed reference strings (e.g. `$rules/verbal.json`) matching the config convention used by `ConfigWalker.resolve_ref`.
- **Strict module boundaries** — each frontend file owns exactly one concern: `api.js` (only file that calls `fetch`), `schema.js` (schema fetching/caching + cross-`$ref` resolution + injecting live filesystem enums via `patchRefEnums`), `templates.js` (hardcoded `TEMPLATES` map per `kind`, not derived from the schema), `editor.js` (only file importing `vanilla-jsoneditor`; one editor instance at a time, destroyed before remount), `main.js` (orchestrates `openFile`/`saveFile`, delegates everything else).
- `kind` is the sole dispatch key for which schema/templates/patches apply — every config file has one.
- `schemaDefinitions` (a `{ './Other.json': schema }` map) must be passed to both the editor and the AJV validator, since e.g. `Paradigm.json` cross-references `./FeatureMarkers.json#/definitions/marker`; omitting it makes those fields silently skip validation.
- `additionalProperties` fields with open-ended string keys (`FeatureMarkers.markers`, `Paradigm.feature_markers`) intentionally get no key autocompletion in the PoC.
