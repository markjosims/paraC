# parts_of_speech
Config files that define the parts of speech in a language along with the features relevant to them.
A part of speech config must correspond to a CSV file in the `data/lexicon` folder, e.g. `adjective.yaml` defines the metadata for adjectives and `adjective.csv` lists adjective lexemes.
`PartOfSpeech` configs must minimally specify the name and list of features for a given part of speech.
A sample `PartOfSpeech` config is given below.
```yaml
kind: PartOfSpeech
name: adjective
features:
  - number
  - gender
```
An optional attribute 'lexical_features' may also be specified.
This describes morphological features which are inherent to the word, like e.g. gender on nouns in Spanish.
This allows features to be listed in the gloss for a word (e.g. perro `dog<m,sg>`) but not associated with any morphological formative in inflection.
```yaml
kind: PartOfSpeech
name: noun
features:
  - number
lexical_features:
  - gender
```
All lexical features must be listed in a column in the relevant CSV file.
For example, if 'gender' were not a column in `noun.csv`, the compiler would throw an error upon reading `noun.yaml`.

The possible values for a lexical feature are specified via a `FeatureDefinitions` config, and, outside of the `PartOfSpeech` class, there is no distinction between a lexical or inflectional feature.
For features like gender, the same feature may be lexical for some parts of speech (e.g. nouns) but inflectional for others (e.g. adjectives).
There may be cases, however, where it is useful to define a feature which is purely lexical, e.g. to signal that a given verb root has irregular inflection, belongs to a particular inflectional class, or takes a different set of suffixes for a particular tense or mood.
For example, we may assign the lexical features 'ablaut_pattern' and 'past_suffix_type' to the part of speech 'verb', which describe the particular pattern of ablaut alternations or past suffixes the verb takes.
```yaml
kind: PartOfSpeech
name: verb
features:
  - tense
  - person
  - mood
lexical_features:
  - ablaut_pattern
  - past_suffix_type
```
The possible values would be specified in a `FeatureDefinitions` file like so:
```yaml
# conjugation_class_features.yaml
kind: FeatureDefinitions
features:
  ablaut_pattern:
  - no_ablaut
  - a_o_ablaut
  - a_e_ablaut
  past_suffix_type:
  - past_suffixes_A
  - past_suffixes_B
  - past_suffixes_C
```
The last optional attribute is 'principal_parts', which also indicates column names in the corresponding CSV file.
This allows specifying a number of alternate stems for a particular root which can be referenced by `Paradigm` objects.
See the [paradigm documentation](config/paradigms/README.md) and [lexicon documentation](config/lexicon/README.md) for more information.
```yaml
kind: PartOfSpeech
name: verb
features:
  - tense
  - person
  - mood
principal_parts:
  - present_stem
  - past_stem
```