Prompt: Review all the files in @src/pages/* and note down any inconsistencies in API or state lifecycle, any sloppy state  
   logic, or any duplicated logic that can be consolidated into shared class(es).                                      

✦ I have reviewed the current editor implementations (inventory.py, feature_values.py, feature_combinations.py,
  feature_markers.py, contingent_markers.py, lexicon.py, paradigm.py, patterns.py, rules.py) and editor_utils.py. Here
  are the identified inconsistencies, sloppy state logic, and opportunities for consolidation.

  1. Inconsistent State Lifecycle & "Sync-on-Render"
  There is a fundamental split in how pages handle state synchronization:
   - lexicon.py and feature_combinations.py: Perform "active" sync by comparing widget return values with current state
     and calling editor.read_form_to_state() + st.rerun() mid-render.
   - paradigm.py and feature_markers.py: Only call read_form_to_state() inside specific action buttons
     (Add/Remove/Save). If a user changes a text field and then clicks an expander, the text field change might be lost
     or lag behind.
   - inventory.py: Rebuilds the entire state from widgets in read_form_to_state but relies on editor_toolbar to trigger
     the sync for the preview.

  Recommendation: Move read_form_to_state() to the top of the page function (after editor_guard) for all editors. This
  ensures that every re-run (even those triggered by Streamlit's internal widget logic) captures the latest user input
  before the next frame is rendered.

  2. Duplicated "Collection Management" Logic
  Almost every editor implements a version of:
   - insert_item() / remove_item()
   - move_item_up() / move_item_down() (only in paradigm.py currently, but useful elsewhere)
   - Clearing widget keys for a specific UUID.

  Recommendation: Create a CollectionEditorMixin or add helper methods to EditorBase that handle UUID-based list
  mutations and key cleanup. FeatureMarkers, ContingentMarkers, Lexicon, and Paradigm all manage lists of dictionaries
  with UUIDs.

  3. Sloppy Marker Syncing
  The logic for syncing Marker objects is duplicated between feature_markers.py and contingent_markers.py:
   - _sync_marker_list is nearly identical in both.
   - render_marker_list and render_marker_row are now in editor_utils.py, which is good, but the back-sync (Widget ->
     Model) is still trapped in the page classes.

  Recommendation: Move _sync_marker_list into editor_utils.py as a static helper or a method on EditorBase. It should
  take the editor instance to use get_node_widget.

  4. Fragmented Registry Construction
   - lexicon.py: Directly calls Lexicon.from_config.
   - paradigm.py: Directly calls Paradigm.from_config.
   - feature_values.py: Uses FeatureValuesRegistry.

  Recommendation: Standardize build_state_from_config to always use the Registry class where possible, as the Registry
  classes often contain the "merging" and "validation" logic that the raw .from_config methods might miss.

  5. UUID Consistency
   - LexiconEditor generates UUIDs for CSV rows on load.
   - ParadigmEditor generates UUIDs for stages and mappings on load.
  If a user clicks "Refresh", new UUIDs are generated, and all existing widget state is orphaned (leaking memory in
  st.session_state until a page switch).

  Recommendation: If possible, derive stable keys from data (e.g., feature_name for mappings) or ensure that
  build_state_from_config is only called when the file path actually changes.

  6. Duplicated Toolbar/Sidebar Boilerplate
  Every page has a nearly identical page() function and toolbar() function.
   - editor_sidebar and editor_header are already consolidated.
   - editor_toolbar could be consolidated into a single component in editor_utils.py that takes "Add" and "Save"
     callbacks.

  7. Explicit "Marker Type" Logic
  In render_marker_row, there is a manual check for marker.type == "replace" or "rule". This logic is duplicated in the
  "back-sync" logic.

  Recommendation: The Marker class (or a wrapper) should handle its own serialization/deserialization logic for the UI,
  rather than the Editors knowing about the internal structure of every marker type.

  ---

  Proposed Action Plan
   1. Refactor EditorBase: Add sync_markers(list[Marker], scope) and mutate_list(list, action, ...) helpers.
   2. Consolidate Marker UI logic: Move the "back-sync" logic for markers into editor_utils.py alongside the renderers.
   3. Global Sync Policy: Update all pages to call read_form_to_state once at the start of the page render.
   4. Standardize Toolbars: Create a generic editor_toolbar in utils.
