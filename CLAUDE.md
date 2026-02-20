# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Morphological parser and inflector for the Tira language (an under-documented Kordofanian language) using Finite State Transducers (FSTs) via Pynini. Parses Tira words into morphological components/glosses, inflects words from roots + feature values, and performs fuzzy corpus search.

## Important: Ongoing Refactor

The codebase is mid-refactor. There are two data flow approaches:

**Old (current runtime) approach:** Morphological data (affixes, paradigm structure, feature values, phonological rules) is hardcoded in Python files under `src/forms/` (e.g., `verb_forms.py`, `form_helpers.py`) and `src/constants/features.py`. These files directly construct Pynini FSTs using inline linguistic data.

**New (target) approach:** Morphological data is declaratively specified in YAML config files under `config/`. The Python code reads these configs and constructs FSTs from them. The new data flow is:
```
config/parts_of_speech/*.yaml  ->  defines POS metadata
config/paradigms/*.yaml        ->  defines paradigm structure, references markers
config/markers/*.yaml          ->  defines morphological formatives (affixes)
config/rules/*.yaml            ->  defines phonological rules
config/patterns/*.yaml         ->  defines reusable FSA patterns
config/features/*.yaml         ->  defines feature definitions and valid combinations
config/inventory/*.yaml        ->  defines phoneme inventory
data/lexicon/*.csv             ->  lexical roots with glosses
```

`src/forms/form_constructors.py` is the first file implementing the new config-driven approach. It defines the dataclasses (`Marker`, `FeatureMarkers`, `ContingentMarkers`, `FeatureValueCombinations`, `ParadigmMarkers`) that the YAML configs get loaded into.

The YAML config READMEs (`config/paradigms/README.md`, `config/rules/README.md`, `data/lexicon/README.md`) document the intended schema. When working on the refactor, these READMEs are the source of truth for how configs should behave.

## Commands

### Install
```bash
pip install -r requirements.txt
pip install -e ".[dev]"
```

Pynini requires OpenFST on macOS (see README.md). On Windows, use WSL.

### Run tests
```bash
pytest tests/
pytest tests/main_parser_test.py          # single test file
pytest tests/main_parser_test.py::test_fn # single test function
```

### CLI
```bash
python -m src.cli parse_word "rá ápà"
python -m src.cli inflect_word ap --tam imperfective --deixis itive --class r
python -m src.cli search_word "àprìɲ"
python -m src.cli search_corpus apri
python -m src.cli get_gloss_for_root ap
python -m src.cli get_root_for_gloss carry
```

### Flask web app
```bash
flask --app src.app.app run
```

## Architecture

### Key modules

- **`src/parser.py`** - Top-level entry points: `parse_word()`, `inflect_word()`, `get_main_parser()`. Composes all paradigm FSTs with tone processes (left H spreading, final lowering).
- **`src/fst_helpers.py`** - FST factory (`fst()`), string encode/decode, lattice path extraction, gloss formatting, symbol table management. The `fst()` factory is used pervasively to create FSTs with consistent symbol tables.
- **`src/forms/`** - Paradigm builders. Currently uses the old hardcoded approach except `form_constructors.py` which implements the new config-driven dataclasses.
- **`src/forms/verb_forms.py`** - Largest paradigm builder (7 FV suffix classes, subject/object person markers, class prefixes). Split across FV class and auxiliary presence.
- **`src/forms/form_helpers.py`** - Shared helpers wrapping `pynini.lib.paradigms` prefix/suffix functions.
- **`src/lexicon/lexicon.py`** - CSV loading with NFKD normalization, root/gloss lookups, lexical flag and principal part handling.
- **`src/lexicon/phonology.py`** - Phonological FSAs and rules (tone association, vowel coalescence, SIGMASTAR definition).
- **`src/search.py`** - Fuzzy FST-based word search (edit transducer) and regex corpus search with ASCII normalization via unidecode.
- **`src/decorators.py`** - `fst_cache()` saves compiled FSTs to `.cache/`; `output_cache()` caches function outputs. Both use MD5 hashing.
- **`src/constants/`** - Feature definitions (`features.py`), phoneme inventory (`symbol_table.py`), path constants (`paths.py`).

### YAML config schema (new approach)

Config files reference each other with `$name` syntax (e.g., `$person_suffixes` imports `config/markers/person_suffixes.yaml`).

- **Paradigms** (`config/paradigms/`): Specify `part_of_speech`, `features` (map feature names to marker configs or literal values), optional `contingent_features`, `order`, `filter`, and `feature_combinations`.
- **Markers** (`config/markers/`): Define morphological formatives. Each marker maps a feature value to an operation: `suffix`, `prefix`, `replace`, `rule`, `suppletion`, or `null` (zero-marking).
- **Rules** (`config/rules/`): Three types: `simple_rule` (wraps `pynini.cdrewrite`), `map_rule` (string mapping), `chain_of_rules` (composed sequence).
- **Patterns** (`config/patterns/`): Named FSA patterns reused in rule contexts.
- **Inventory** (`config/inventory/`): Phoneme definitions (segments, tones) with flags.

### Caching

Compiled FSTs are cached to `.cache/`. When changing config or form-building code, stale caches may cause unexpected behavior. Delete `.cache/` to force recompilation.

## Tira language notes

- Tira has complex tonal morphology including left H spreading and final lowering.
- Verbs have 7 FV (final vowel) suffix classes organized into 3 morphomes.
- Verb paradigms are split by FV class and auxiliary presence because auxiliaries can coalesce with verb stems.
- Class prefixes encode noun class agreement (single-letter codes like `g`, `r`, `l`, etc.).
- Transcription data is inconsistent across sources; fuzzy search accounts for IPA variation.

## TODO
- [x] Update Reserved symbols to reflect changes in config/inventory/README.md (use `<angle brackets>` instead of backslash and add `<Empty>` symbol)
- [x] Fix bolding issue in Inventory preview (voiced stops unbolded for some reason)
- [x] Don't expose directory structure to user directly. Instead, user only sees Features, Inventory, Markers, Paradigms, Part of Speech and Rules tabs.
  - Upon creating a new config, users are prompted only with the NAME and TYPE. The app handles directory location automatically
  - Directory map:
    - Inventory > `config/inventory`
    - FeatureDefinition, FeatureCombinations > `config/features`
    - Rules > `config/rules`
    - Paradigms > `config/paradigms`
    - PartsOfSpeech > `config/parts_of_speech`
    - Patterns > `config/patterns`
    - FeatureMarkers, ContingentFeatureMarkers > `config/markers`
- [x] Make it clear to the user when the current config has unsaved changes, and prompt to save when navigating out of config or closing tab
- [x] Allow the user to rename a config file
- [x] Change Pattern preview in right tab to show the `<REPR>` of the pattern
  - Upon clicking on the preview, it should display the underlying RegEx string
- [ ] ~~Treat class `<REPR>`'s defined in the Inventory as Patterns in the right display tab~~ (reverted — Inventory classes shown hierarchically in Inventory section instead)
- [x] Clicking on the preview of a Rule should display following:
  - User description, if any
  - A regex shorthand for the rule equivalent to {input_pattern} > {output_pattern} / {left_context} _ {right_context}
