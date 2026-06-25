# Feature API

Pages @src/pages in should have a consistent interface for interacting with `Feature` objects from the `Grammar`.

## Rules

1. Remove all references to `features_to_values`.
    This attribute has been deprecated and removed.
2. Always load in `Feature` objects where possible.
3. Move duplicated logic to @src/pages/editor_utils.py.
    This should at least include adding a new helper `feature_multiselect` which allows the user to pick multiple feature values that are saved to some key in the editor state as this logic is repeated across @src/pages/lexicon.py, @src/pages/contingent_markers.py and @src/pages/morpheme_set.py.
4. Import classes at top of module (if not imported already).
    NEVER import inside a function call.

    ```python
    from src.grammar import Grammar
    from src.grammar.registry.feature_values_registry import Feature
    from src.grammar.orchestrator.feature_orchestrator import FeatureOrchestrator
    from src.pages.editor_utils import feature_multiselect
    ```

5. Use typing hints for linting and autocompletions in IDE:

    ```python
    grammar: Grammar = st.session_state.grammar
    feature_orchestrator: FeatureOrchestrator = grammar.feature_orchestrator
    features: list[Feature] = self.data['features']
    ```

## Implementation Notes

### 1. `Feature` Class Enhancements

- Add `__lt__` to `src/grammar/registry/feature_values_registry.py:Feature` to allow direct sorting of `Feature` objects by their name.

### 2. Standardized State Management

- All Streamlit editors should store `Feature` class instances in their `self.data` (e.g., `self.data["features"] = [Feature(...), ...]`).
- Conversion back to strings for YAML serialization must happen in the `to_yaml()` method using the `Feature.name` attribute.
- Pages to update: `lexicon.py`, `contingent_markers.py`, `morpheme_set.py`, `paradigm.py`, `morpheme_sequence.py`, and any others in `src/pages/`.

### 3. `editor_utils.py` Helpers

- `feature_multiselect(label, editor, key_prefix, help_str)`:
  - Automatically retrieves available features from `st.session_state.grammar.feature_orchestrator.features`.
  - Uses `format_func=lambda f: f.name` for the `st.multiselect`.
  - Detects changes and calls `st.rerun()` to ensure the UI updates immediately (important for editors where feature selection changes table columns).
  - Updates `editor.data["features"]` (or specified key) directly.

### 4. Cleanup

- Remove any remaining `features_to_values` logic in registries or tests if they were primarily serving the UI.
- Ensure `Feature.values` is used when a list of available values is needed for a specific feature.
