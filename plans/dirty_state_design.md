# Design: Dirty State Tracking & Intelligent Backend Syncing

This document outlines the strategy for implementing "Dirty State" logic in the Tira Parser editors and integrating it with the grammar orchestrators to minimize redundant FST compilation and improve UX.

## 1. The Core Problem

Currently, the grammar re-initialization is "all or nothing." If a user modifies a single character in a lexicon CSV or a rule YAML:

1. The `Grammar` object may be re-initialized.
2. All registries reload their respective config directories.
3. The `FstOrchestrator` may rebuild all main graphs (Parser/Inflector), which is a computationally expensive operation involving thousands of compositions and unions.

## 2. Dirty State Tracking in the UI

### Implementation in `EditorBase`

We will add a snapshotting mechanism to the base editor class.

* **`_snapshot: str | None`**: Stores a YAML-serialized version of the data exactly as it exists on disk.
* **`is_dirty` (Property)**: Returns `True` if `yaml.dump(self.to_yaml()) != self._snapshot`.
* **`reset()`**: Reverts `self.data` to the state stored in `_snapshot`.

### Granular Dirty Tracking

For "Collection" editors (Rules, Patterns, Lexicon), we should track dirtiness at the **item level**:

* Each item (e.g., a `Rule` object) receives a `_snapshot` field.
* The editor can identify exactly *which* rule changed.
* **Benefit**: If only a "test mapping" changed, we don't need to inform the backend at all, as test mappings don't affect the compiled FSTs.

## 3. Backend Integration (The "Delta" Protocol)

Currently, the orchestrators take a directory and find everything. To optimize, we need an "Incremental Update" API.

### Registry Updates

Registries should support a `patch(name, new_config)` method:

```python
def patch(self, name: str, config: dict):
    # Update only the specific object in self.data
    # Mark the registry itself as 'stale'
    self.is_stale = True
    self.data[name] = self.load_data_from_config(config)
```

### Intelligent FST Re-compilation

The `FstOrchestrator` is the biggest bottleneck. It should use the dirty state to perform surgical updates:

1. **Dependency Graph Awareness**: If a `Pattern` changes, only the `Rules` that reference that pattern need their transducers rebuilt.
2. **Partial Graph Building**: If a single `Paradigm` is modified, we only rebuild the `inflect_graph` and `parse_graph` for *that* POS, rather than the entire language's grammar.
3. **Lexical Hashing**: Store a hash of each Lexicon CSV. If the root/gloss hasn't changed but a principal part did, only rebuild the `principal_part` transducer, skipping the expensive `get_filtered_roots` logic.

## 4. User Experience (UX) Enhancements

### Visual Cues

* **Sidebar Labels**: Files with unsaved changes appear with a `*` or a colored dot (e.g., `verb.yaml [dirty]`).
* **The "Save" Button**: Highlight the Save button (e.g., make it primary/pulsing) only when the state is dirty.
* **Confirmation Guards**: If a user tries to "Open" a new file or "Refresh" while the current file is dirty, show a `st.warning` with "Discard changes?" or "Save first?".

### The "Diff" View

Add a dedicated tab in the editor that uses `difflib` to show a side-by-side comparison of the current buffer vs. the disk. This allows linguists to review their phonological changes before committing them to the grammar.

## 5. Implementation Phases

1. **Phase 1 (UI Only)**: Implement `_snapshot` and `is_dirty` in `EditorBase`. Add "Unsaved Changes" indicators to the Streamlit header.
2. **Phase 2 (Granular Sync)**: Refactor `read_form_to_state` to return a `set` of modified item UUIDs.
3. **Phase 3 (Orchestrator API)**: Add `update_item` methods to `Grammar` and `FstOrchestrator` to allow reloading single components without a full reboot.
4. **Phase 4 (Incremental UI)**: Add the "Diff" view and "Discard Changes" functionality.
