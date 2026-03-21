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
An optional attribute 'invariant_features' may also be specified.
This describes morphological features which are inherent to the word, like e.g. gender on nouns in Spanish.
This allows features to be listed in the gloss for a word (e.g. perro `<dog,m,sg>`) but not associated with any morphological formative in inflection.
```yaml
kind: PartOfSpeech
name: noun
features:
  - number
invariant_features:
  - gender
```
All invariant features must be listed in a column in the relevant CSV file.
For example, if 'gender' were not a column in `noun.csv`, the compiler would throw an error upon reading `noun.yaml`.

Another optional attribute is 'lexical_flags'.
Each value of 'lexical_flags' is the name of a column in the CSV file.
Lexical flags are used to define special behavior for particular lexemes or lexical classes, e.g. to signal that a given verb root has irregular inflection, belongs to a particular inflectional class, or takes a different set of suffixes for a particular tense or mood.
See the [lexicon documentation](data/lexicon/README.md) for more information.
```yaml
kind: PartOfSpeech
name: verb
features:
  - tense
  - person
  - mood
lexical_flags:
  - ablaut_pattern
  - past_suffixes
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