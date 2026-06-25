# Editor state lifecycle

## Audit

General questions:

- **Loading:** Most classes use `.from_config`. `Rule.from_config` was destructive but is now fixed.
- **Updating state:** Handled via Streamlit session state and `read_form_to_state`.
  - *Inconsistency:* Some pages sync to raw `dict` in `self.data` (lexicon, paradigm), others sync directly to model objects (rules, features, inventory).
  - *Validation:* Minimal. Errors during sync (like bad regex or missing `=>` in string maps) can cause crashes or bad YAML.
- **Writing to YAML:** Standardized to use `.to_dict()` methods in the model/registry layer. All target editors have been refactored to use this approach.
- **Syncing with Grammar:** Users need a "Dirty" flag or a "Rebuild Grammar" button when changes are made but not yet compiled into FSTs.
- **Fetching from Grammar:** Editors now fetch live objects (Features, Rules, Lexicons) from `st.session_state.grammar` for high-fidelity serialization.

### Summary of Audit

Most pages follow a "Load -> Session State -> Edit -> Registry.to_dict -> Write" flow. Implementation of `.to_dict()` has moved serialization logic out of the UI layer.

The next critical phase is **Input Validation** and **Dirty State Tracking**.

## Validation Requirements

| Component | Target Field | Failure Case | Strategy |
|-----------|--------------|--------------|----------|
| **Rules** | String Map | Missing `=>` separator | Skip line + `st.error` summary. |
| **Rules** | Regex (Acceptor) | Invalid FST syntax (e.g. `[a-z`) | Try `Acceptor(val)` in `read_form_to_state`. Catch `Exception` → `st.error`. |
| **Patterns** | Pattern Text | Invalid FST syntax | Try `Acceptor(val)` → catch `Exception` → `st.error`. |
| **Inventory** | Item Value | Flag missing `[]` or Class missing `<>` | Enforce `[...]` for flags, `<...>` for classes. `st.error` if missing. |
| **Inventory** | Item Value | Re-use `ReservedSymbols` (e.g. `#`, `*`) | Check against `ReservedSymbolMixin.reserved_symbols`. `st.error` if reserved. |
| **Features** | Feature Name | Duplicate name in same file | Check `self.data["id_map"]` → `st.error`. |
| **Features** | Values | Empty value (excluding unmarked) | Filter empty strings + `st.warning`. |
| **Markers** | Value | Malformed `$` reference | Use `validate_file_reference_str`. If result missing `$`, `st.error`. |
| **Markers** | Value | Invalid FST syntax (realizations) | Try `Acceptor(val)` → catch `Exception` → `st.error`. |
| **Paradigm** | Fixed Features | Value not in Feature's domain | Fetch `Feature` from `Grammar` → check `val in feature.values`. `st.error` if invalid. |
| **Lexicon** | Root / Morpheme | Invalid FST syntax | Treat as pattern: try `Acceptor(val)` → catch `Exception` → `st.error`. |
| **Lexicon** | CSV Columns | Missing required `root` or `gloss` | Assert presence during sync. `st.error` if column removed. |
| **MorphemeSet**| Morpheme Value | Invalid FST syntax | Try `Acceptor(val)` → catch `Exception` → `st.error`. |
| **MorphemeSeq**| Step Value | Invalid FST syntax | Try `Acceptor(val)` → catch `Exception` → `st.error`. |

### Suggested Implementation

1. **Non-blocking Errors**: Use `st.error` in the widget rendering loop or `editor_header`. Allow the UI to remain interactive but disable the **Save** button via a `valid` flag in `EditorBase`.
2. **Explicit Validation Methods**: Add `validate(self) -> list[str]` to `EditorBase`. Call it in `editor_header`.
3. **Model-Level Guards**: Leverage `InventoryItem` and `InventoryClass` `__post_init__` validation during `read_form_to_state`.

## Plan

1. [DONE] Implement `.to_dict()` for all Registry/Model classes.
2. [DONE] Refactor `EditorBase.to_yaml` in all editors to use centralized serialization.
3. [TODO] Add "Dirty" state tracking to `st.session_state` to prompt grammar rebuilds.
    - Set `st.session_state.grammar_dirty = True` in `save()`.
    - Display warning in sidebar if dirty.
4. [TODO] Enhance `read_form_to_state` with explicit validation and `st.error`.
    - [ ] **Rules/Patterns**: Wrap `Acceptor` creation in try/except; validate `=>` in maps.
    - [ ] **Inventory**: Enforce `[]`/`<>` and check `ReservedSymbols`.
    - [ ] **Feature Values**: Check for uniqueness.
    - [ ] **Markers/Paradigm/MorphemeSet**: Consolidate `$` validation and FST syntax checks.
    - [ ] **Lexicon**: Validate CSV structure and FST patterns for roots/morphemes.
5. [TODO] Standardize `read_form_to_state` sync targets (Model vs Dict).
    - Prefer syncing to Model objects where they exist to leverage internal validation.
