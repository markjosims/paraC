# markers
YAML files for defining morphological formatives for a given feature or feature combination.
Use `FeatureMarkers` to define formatives for a single feature, and `ContingentFeatureMarkers` for formatives that apply to multiple features at once.

## FeatureMarkers
This file gives a paradigm of formatives for a single feature.
The 'feature' attribute indicates the name of the feature marked, and the 'markers' attribute is a list of dictionaries describing the formative for each value of the feature.
See [Marker keys](#marker-keys) for more details.
```yaml
# person_markers_a_stem.yaml
kind: FeatureMarkers
feature: person
markers:
  1sg:
    kind: suffix
    value: -o
  2sg:
    kind: suffix
    suffix: -as
  3sg:
    kind: suffix
    suffix: -a
```

## ContingentFeatureMarkers
This file gives a subparadigm of formatives for two feature sets at once.
This is helpful for cases where the morphological realization of one feature depends on the value of another feature.
The given features are specified using the 'outer_feature' and 'inner_feature' attrs, and the markers are specified using nested objects.
```yaml
# person_tense_markers_a_stem.yaml
kind: ContingentFeatureMarkers
outer_feature: tense
inner_feature: person
markers:
- outer_feature_value: present
    inner_feature_values:
      1sg:
        kind: suffix
        value: -o
      2sg:
        kind: suffix
        value: -as
      3sg:
        kind: suffix
        value: -a
- outer_feature_value: past
  inner_feature_values:
    1sg:
      kind: suffix
      value: -é
    2sg:
      kind: suffix
      value: -aste
    3sg:
      kind: suffix
      value: -ó
```

## Marker keys
The marker dictionary corresponds to the `Marker` class in `src/forms/form_constructors.py`.
This object describes the logic for building an FST describing a morphological formative.
In the Spanish examples above, the only formative kind used is 'suffix,' but several kinds of string operations are allowed, including:
- Suffix: Append suffix string to stem
- Prefix: Prepend prefix string to stem
- Replace: List of ["intab", "outtab"]. Replace "intab" with "outtab" across all contexts.
- Rule: Name of rule to be applied to stem. Must be defined in a `Rules` YAML file.
- Suppletion: Replace the entire stem with the given string.
Note suppletion is not **not** compatible with any of the above operations, and attempting to combine them will throw an error when compiling the marker.
- Principal part: Functionally equivalent to suppletion where the value specifies a column in a given lexicon file and the output string of the process is the value for that column.
See [Princpal Parts](#principle-parts) for more information.

The kind of formative is indicated with the `kind` attr and the `value` attr contains string to be interpreted as a formative.
A marker may contain a single formative or multiple formatives stored as a list.

See below for examples of all rule kinds with a toy language:
```yaml
# toy_person_markers.yaml
kind: FeatureMarkers
feature: person
markers:
  # e.g. ket > pe-ket-ap
  1sg:
  - kind: suffix
    value: -ap
  - kind: prefix
    value: ke-
  # e.g. ket > gat
  2sg:
  - kind: replace
    value: [e, a]
  - kind: rule
    value: $initial_voicing
  # no change, e.g. ket > ket
  3sg: null
  # e.g. ket > pok
  1pl:
    kind: suppletion
    value: pok
  # e.g. ket > re-keet
  2pl:
  - kind: rule
    value: $vowel_lengthening
  - kind: prefix
    value: re-
  # e.g. ket > kets
  3pl:
    kind: rule
    value: $affrication
    
```
Sometimes different formatives can interact and feed each other, e.g.:
```yaml
kind: FeatureMarkers
feature: person
markers:
  1sg:
  # e.g. ked > ket-te
  - kind: suffix
    value: -te
  - kind: replace
    value: [dt, tt]
```
Here, the *-te* suffix feeds the assimilation /dt/.
If assimilation applies before suffixation, we'd get a malformed output \*ked-te.
We need to make sure suffixation precedes assimilation.

To do this, we can use the 'order' key which determines the formative's order of application relative to other processes.
The value of 'order' is not a numeric, it is instead a string which names a unique stage during which the process is applied.
For example, we can define 'suffixation' and 'stem_assimilation' as the names of the two stages.
```yaml
kind: FeatureMarkers
feature: person
markers:
  # e.g. ked > ked-ap
  1sg:
    kind: suffix
    value: -ap
  2sg:
  # e.g. ked > ket-te
  - kind: suffix
    value: -te
    stage: suffixation
  - kind: replace
    value: [dt, tt]
    stage: stem_assimilation
```
Since stages are identified by their name rather than a numeric value, a stage order needs to be specified which determines the sequence of processes.
This is done in the `Paradigm` config, see the [documentation](config/paradigms/README.md) for more details.

## Composition and inheritance
Other YAML configs can be imported into the current file.
In [ContingentFeatureMarkers](#contingentfeaturemarkers) we demonstrate an example of this by importing a `FeatureMarkers` subparadigm into a `ContingentFeatureMarkers` config.
This can also be done at the head of the file with the 'inherits' attribute, e.g.:
```yaml
# person_markers_oy_1sg_present.yaml
kind: FeatureMarkers
inherits: $person_markers_a_stem_present
features: person
markers:
  1sg:
    kind: suffix
    value: -oy
```
This allows easy creation of irregular or sub-regular paradigms where only a few forms differ from some other paradigm specified in the 'inherits' attribute.
The example above could be applied to the Spanish verbs *dar* and *estar*, which take regular a-stem suffixes in the present tense except for the 1sg form which instead takes the suffix *-oy* (ignoring for now the accent on *está*, *estás* and *están*).

We can also use inheritance with `ContingentFeatureMarkers` config files, which e.g. allows us to create a paradigm for the present and past tense forms of *estar*.
```yaml
# person_tense_markers_oy_1sg.yaml
kind: FeatureMarkers
inherits: $person_tense_markers_a_stem_present
features: person
markers:
  tense:
    present:
      1sg:
        kind: suffix
        value: -oy
    past:
      1sg:
        kind: suffix
        value: -uv-e
      2sg:
        kind: suffix
        value: -uv-iste
      3sg:
        kind: suffix
        value: -uv-o  
```
For a verb like *dar*, which takes a-stem suffixes in the present (excepting 1sg *-oy*) and e/i-stem suffixes in the past, we can use inheritance and overriding multiple times in the same file.
```yaml
# person_tense_markers_dar.yaml
kind: FeatureMarkers
feature: person
markers:
  tense:
    present:
      inherits: $person_markers_a_stem_present
      1sg:
        suffix: -oy
    past:
      inherits: $person_markers_ei_stem_past
      1sg:
        suffix: -i
```

## Global attributes and markers
A `FeatureMarkers` or `ContingentFeatureMarkers` config may specify the order globally, rather than needing to define it for every marker individually.
For example, imagine that all tense markers apply at the 'inner suffixation' stage and all person markers at the 'outer suffixation' stage.
Rather than write the 'order' attribute for each marker, we can specify it under 'global_order'.
```yaml
kind: FeatureMarkers
feature: tense
global_stage: inner suffixation
markers:
  present: null
  past:
    kind: suffix
    value: -et
  future:
    kind: suffix
    value: -ol
```

```yaml
kind: FeatureMarkers
feature: person
global_stage: outer suffixation
markers:
  1sg:
    kind: rule
    value: $palatalization
  2sg:
    kind: suffix
    value: -ek
  3sg:
    kind: suffix
    value: -ut
```
If an individual marker specifies the same attribute as a global attribute, the individual marker's specification for that attribute will win.
```yaml
kind: FeatureMarkers
feature: person
global_stage: outer suffixation
markers:
  1sg:
    kind: rule
    value: $palatalization
    stage: stem_mutation
  2sg:
    kind: suffix
    stage: -ek
  3sg:
    kind: suffix
    stage: -ut
```
Rather than assgining a single attribute for all markers in the config, we may wish to apply an entire marker to all forms, and then let each feature value add it's own marker if needed.
For example, let's create a paradigm for the Spanish verb *estar* where we insert a suffix *-uv* to the past tense stem before the person marker:
```yaml
kind: FeatureMarkers
feature: person
global_markers:
- kind: suffix
  stage: -uv
  stage: "Inner suffix"
markers:
  1sg:
    kind: suffix
    stage: "-e"
    stage: "Outer suffix"
  2sg:
    kind: suffix
    stage: "-iste"
    stage: "Outer suffix"
  3sg:
    kind: suffix
    stage: "-o"
    stage: "Outer suffix"
```
While in this case the added effort of specifying the suffix order here outweighs the effort of simply writing out "-uv-e", "-uv-iste", "-uv-o", we present this case as a demonstration of how 'global_markers' may be applied.

## Principle parts
A lexical class may specify multiple principle parts, e.g. a unique present and past stem.
In order to select these stems for a given formative, a 'principal_part' Marker class may be used.

[TODO] give example usage...