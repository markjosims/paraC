# paradigms
Configs defining inflectional paradigms.
The name 'paradigm' here is agnostic to *exhaustive* or *sub-*paradigms.
For example, a `Paradigm` config may correspond to all possible inflected verb forms for an entire language (not recommended), or a sub-paradigm for a specific TAM value for a particular conjugation class (recommended).
An inflectional paradigm must have at minimum the attributes 'part_of_speech' and 'feature_markers'.
```yaml
kind: Paradigm
part_of_speech: verb
feature_markers:
  person: $person_suffixes
  tense: present
  mood: $mood_stem_vowel
```
The 'feature_markers' attribute may contain the name of a `FeatureMarkers` config corresponding to that feature or string indicating a single feature value.
Here we import 'features/person_suffixes.yaml' and 'features/mood_stem_vowel.yaml' to mark the person and mood features respectively.
If the latter, only that feature will be used for the paradigm, and the feature will be zero-marked.
```yaml
kind: Paradigm
part_of_speech: verb
feature_markers:
  person: $person_suffixes
  tense: present
  mood: $mood_markers
```
The 'contingent_features' attribute may be specified alongside 'feature_markers', which imports a `ContingentFeatures` config or list of configs.
```yaml
kind: Paradigm
part_of_speech: verb
feature_markers:
  person: $person_suffixes
  tense: $tense_markers
  mood: $mood_stem_vowel
contingent_markers:
  - $past_tense_person_markers
```
The 'feature_combinations' attribute may be used to specify what combinations of features are possible for the given paradigm by importing a `FeatureCombinations` config.
A single `FeatureCombinations` object is used for the entire paradigm, and it must specify all features for the given part of speech.
```yaml
kind: Paradigm
part_of_speech: verb
feature_markers:
  mood: imperative
  person: $imperative_suffixes
feature_combinations: $imperative_person_values
```
The 'order' attribute allows specifying the order of application of markers, e.g.:
```yaml
kind: Paradigm
part_of_speech: verb
order: [person_suffix, stress_assignment, diphthongization]
feature_markers:
  person: $person_suffixes
  tense: $tense_stem
  mood: $mood_stem_vowel
contingent_markers:
  - $past_tense_person_markers
```
Where the various `FeatureMarkers` and `ContingentFeatureMarkers` configs must reference the stages enumerated in the 'order' attribute.
Any rules that lack an 'order' attribute will be applied last, following all ordered markers.
While ordering is optional, we strongly recommend treating it as obligatory to prevent unexpected interactions between different morphological formatives.

The 'filter' attribute allows the paradigm to select certain lexical roots and not others.
For example, we could create a paradigm that selects only Spanish verbs that exhibit an alternation between *n* and *ng* (e.g. tener/tengo/tienes).
Assuming this is indicated in the [lexicon](data/lexicon/README.md) with a lexical feature "stem_alternation=n_ng_alternation", we can do this by selecting only verbs with this tag.
```yaml
kind: Paradigm
part_of_speech: verb
filter:
  lexical_features:
  - [stem_alternation, n_ng_alternation]
feature_markers:
  person: $person_suffixes_with_stem_change
  tense: $tense_stems
contingent_markers:
  - $past_tense_person_markers
```
We can also select for multiple lexical flags at once, for example if we want to target verb roots that under *n~ng* alternation and *o~ue/e~ie* alternation simultaneously in Spanish.
```yaml
kind: Paradigm
part_of_speech: verb
filter:
  lexical_features:
  - [stem_alternation, n_ng_alternation]
  - [vowel_alternation, diphthongization]
feature_markers:
  person: $person_suffixes_with_stem_change
  tense: $tense_stems
contingent_markers:
  - $past_tense_person_markers
```
We might also select every root that fits some phonological shape using the 'pattern' attr.
For example, imagine a language where disyllabic verb roots take different suffixes than monosyllabic verb roots in the past tense.
The value must be the 'repr' of a pattern described in a `Patterns` class.
```yaml
kind: Paradigm
part_of_speech: verb
filter:
  pattern: "<TwoSyllableWord>"
feature_markers:
  person: $disyllabic_person_markers
  tense: past
```

```yaml
kind: Paradigm
part_of_speech: verb
filter:
  pattern: "<MonoSyllableWord>"
feature_markers:
  person: $monosyllabic_person_markers
  tense: past
```

Paradigms may also declare 'global_markers' much like `FeatureMarkers` and `ContingentMarkers`.
This may be useful when enforcing a particular stem shape across an entire paradigm, for example.
```yaml
kind: Paradigm
part_of_speech: verb
global_markers:
- kind: principal_part
  value: past_stem
- kind: rule
  value: $LLH_melody
feature_markers:
  tense: past
  person: $past_tense_person_suffixes
```