# todo
## Web app
### Pages
- [x] Interactive I/O testing in rule editor
- [x] Feature editor
- [x] Replace stateful `FstRegistry` with `GrammarRegistry`
- [x] Feature combinations editor
- [x] Marker editor
- [x] Paradigm editor
- [ ] Validate editor values against registry
    - [ ] Feature combinations
    - [x] Markers
    - [x] Paradigm
### UI/UX
- [ ] 'Save YAML button' sticks to top of page
- [X] Option to rename or delete YAML files
- [X] Add easy interface for combining diacritics
    - Checkbox "Combining diacritics" opens a menu of buttons with common diacritics
    - String stored as "DIAC:á"
    - Simple dictionary lookup maps user-friendly version to unicode point for combining diacritics
## Parser backend
- [x] Rename `FeatureValuesRegistry` to `FeatureValuesRegistry`
- [x] `FeatureValuesRegistry` orchestrates `FeatureValuesRegistry` and `FeatureCombinationsRegistry`
- [x] Marker registries pass tests
- [-] Implement `GrammarRegistry`
    - Orchestrates **all** registries for an entire language project
    - [x] Start by just encapsulating `FstRegistry`, `FeatureValuesRegistry` and `MarkerRegistry`
- [-] Implement `Paradigm` class
    - [-] Orchestrates `FeatureValuesRegistry`, `FstRegistry`, `MarkerRegistry`
    - [-] Query features set -> `List[Marker]`
    - [-] Easy I/O verification of `$stem` -> `List[Marker]` -> `$inflected_form` using `Paradigm.inflect_stem(stem, features) -> pynini.Fst` method
    - [-] `Paradigm.output_paradigm(stem) -> List[Dict[str, str]]` gives a list of **all inflected forms* for a given stem that the paradigm supports
        - include `require_features: Dict[str, List[str]]` and `exclude_features: Dict[str, List[str]]` args to constrain feature space (e.g. passing `require_features={"class": ['l', 'unmarked']}` will only output verb forms marked with 'l' class or with an unmarked class value)
- [-] Implement `PartOfSpeechRegistry` with child class `Lexicon`
- [-] Define logic for filtering stems belonging to a particular paradigm
    - [x] Migrate 'lexical flag' to existing 'invariant_feature' attribute
- [x] All `from_config` factory functions should expect other registry kinds to be passed, they should **not** be built eagerly
- [x] Main graphs for form <==> gloss transduction
- [ ] Rules/markers may reference lexical features
- [ ] Sample paradigms with nouns
## Backburner
- [ ] Error messages should trigger logs, and the code for this should be DRY.
- [ ] Audit & document auto-generated web code