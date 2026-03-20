# todo
## Web app
### Pages
- [x] Interactive I/O testing in rule editor [!CLAUDE]
- [ ] Feature editor [!CLAUDE]
    - Instantiate a `ParadigmRegistry` (orchestrates ALL child registries!)
- [ ] Feature combinations editor
    - Should check against `FeatureRegistry` that features and values are supported
- [ ] Marker editor
    - Should also validate against `FeatureRegistry`
- [ ] Paradigm editor
### UI/UX
- [ ] Save YAML button sticks at top of page
- [ ] Option to rename or delete YAML files
## Parser backend
- [x] Rename `FeatureRegistry` to `FeatureValuesRegistry` [!MARK]
- [x] `FeatureRegistry` orchestrates `FeatureValuesRegistry` and `FeatureCombinationsRegistry` [!MARK]
- [x] Marker registries pass tests
- [ ] Implement `PartOfSpeechRegistry` with child class `Lexicon`
- [ ] Implement `Paradigm` class
    - Orchestrates `FeatureRegistry`, `FstRegistry`, `MarkerRegistry`
    - Query features set -> `List[Marker]`
    - Easy I/O verification of `$stem` -> `List[Marker]` -> `$inflected_form`
- [ ] Implement `ParadigmRegistry`