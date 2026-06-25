# Morpheme sequences

Add new grammar modules to better handle concatenative morphology and sequencing of lexical and morphological elements.
Consider that a `Paradigm` takes a `Lexicon` and a set of operations (consisting of `FeatureMarkers` and `ContingentFeatureMarkers`) and produces fully inflected words, defining morphotactics for how operations are applied to each feature combination for each root.
A `MorphemeSequence` class takes a list of "morphemes" and defines morphotactics for how these may be sequenced.
"Morpheme" here may be 1. members of a `Lexicon` class, 2. a `Paradigm` class (necessary for `Lexicon` classes with inflectional features) and 3. a simple `Pattern` string to be inserted between two `Lexicon` or `Paradigm` members or 4. a `Rule` to apply to all prior input.

## Demonstration with data

Similar to a `Paradigm`, the primary functionality of a `MorphemeSequence` is to define a bijection between fully inflected strings and tuples of a morphological feature vector and lexical root (or many, in the case of `MorphemeSequence`).
The inflectional features that constitute a feature vector for a `MorphemeSequence` is the union of the lexical features of all of its constituent `Lexicon` and the lexical and inflectional features of `Paradigm` objects.
Recall that `Lexicon` object specifies a set of inflectional and lexical features.
Lexical features are fixed for each lexicon entry (e.g. 'perro' is fixed for masculine in Spanish, or 'ðɔ̀nd̪ɔ̀' is fixed for class ð in Tira), whereas inflectional features require some rule for exponing them.
`Paradigm` objects provide logic for exponing a feature using morphological operations defined in `FeatureMarkers` or `ContingentFeatureMarkers`.
Without a `Paradigm` object, a `Lexicon` has no internal logic for interpreting its own inflectional features.
For this reason, we ignore the inflectional features of any `Lexicon` objects in a `MorphemeSequence`.

When combined in a `MorphemeSequence`, we assume that all morphemes in a sequence must have the same feature specification for the *intersection* of their inflectional and/or lexical features.
Consider nominal marking in Tira.
Nouns in Tira are marked for singular and plural number, and nominative or accusative case.
Number is exponed by the noun's class prefix, e.g.

- ð-àŋàl    Clð-sheep.sg
- j-àŋàl    CLj-sheep.pl

- ð-ɔ̀nd̪ɔ̀    Clð-gourd.sg
- r-ɔ̀nd̪ɔ̀    Clð-gourd.pl

- l-òló     CLl-elbow.sg
- ŋ-òló     CLl-elbow.pl

- -ùt̪ùlú    CLg-spider.sg
- l-ùt̪ùlú   CLl-spider.pl

Note that some class prefixes, e.g. CLg, are empty, and that a single prefix may be both singular and plural, e.g. *l-*.
Case is marked by a suffix, which is orthogonal to number and class.

- ð-àŋàl-à  Clð-sheep.sg-ACC
- j-àŋàl-à  CLj-sheep.pl-ACC

- ð-ɔ̀nd̪-à   Clð-gourd.sg-ACC
- r-ɔ̀nd̪-à   Clr-gourd.pl-ACC

- l-òl-á    CLl-elbow.sg-ACC
- ŋ-òl-á    CLl-elbow.sg-ACC

- -ùt̪ùl-á   CLg-spider.sg
- l-ùt̪ùl-á  CLl-spider.pl

We can represent this as a `MorphemeSequence` e.g. `ClassPrefix-NounStem-CaseSuffix-HiatusResolution`, where `HiatusResolution` is a `Rule` that elides a vowel preceding the accusative suffix and all other members of the sequence are `Lexicon` objects.
Consider how this pattern may be captured by sequencing `Lexicon` classes and constraining their possible permutations.

Let the following features and values be defined:

- `noun_class_sg`: e.g. 'ð', 'r', 'j', the class a noun takes when marked with singular number
- `noun_class_pl`: e.g. 'ð', 'r', 'j', the class a noun takes when marked with plural number
- `noun_case`: 'ACC' or 'NOM'

We then define a `Lexicon` class for `ClassPrefix` with `noun_class_sg` and `noun_class_pl` as lexical features, e.g:

```csv
root,noun_class_sg,noun_class_pl
j-,,j
ð-,ð,
r-,,r
l-,l,
l-,,l
-,g,
ŋ-,,ŋ
```

And `NounStem` as a `Lexicon` class with the same lexical features.

```
root,gloss,noun_class_sg,noun_class_pl
àŋàl,sheep,ð,j
ɔ̀nd̪ɔ̀,gourd,ð,r
òló,elbow,l,ŋ
ùt̪ùlú,spider,g,l
```

Whereas a prefix is paired with a single number/class feature and the other is left unmarked, nouns have both features specified.
By allowing empty features in one morpheme to match with any feature specification for another, we can properly control the prefix<-->noun pairings.

```
- ð-àŋàl    sheep[noun_class_sg=ð,noun_class_pl=unmarked]
- j-àŋàl    sheep[noun_class_sg=unmarked,noun_class_pl=j]

- ð-ɔ̀nd̪ɔ̀    gourd[noun_class_sg=ð,noun_class_pl=unmarked]
- r-ɔ̀nd̪ɔ̀    gourd[noun_class_sg=unmarked,noun_class_pl=r]

- l-òló     elbow[noun_class_sg=l,noun_class_pl=unmarked]
- ŋ-òló     elbow[noun_class_sg=unmarked,noun_class_pl=ŋ]

- -ùt̪ùlú    spider[noun_class_sg=unmarked,noun_class_pl=g]
- l-ùt̪ùlú   spider[noun_class_sg=unmarked,noun_class_pl=l]
```

Since case is orthogonal to number and class, we define a trivial `Lexicon` object with two records:

```
root,case
,nom
-a,acc
```

Which gives us the following sequences:

```
- ð-àŋàl    sheep[noun_class_sg=ð,noun_class_pl=unmarked,case=nom]
- ð-àŋàl-a  sheep[noun_class_sg=ð,noun_class_pl=unmarked,case=acc]
- j-àŋàl    sheep[noun_class_sg=unmarked,noun_class_pl=j,case=nom]
- j-àŋàl-a  sheep[noun_class_sg=unmarked,noun_class_pl=j,case=acc]

- ð-ɔ̀nd̪ɔ̀-a  gourd[noun_class_sg=ð,noun_class_pl=unmarked,case=nom]
- ð-ɔ̀nd̪ɔ̀-a  gourd[noun_class_sg=ð,noun_class_pl=unmarked,case=acc]
...
```

We then apply the `HiatusResolution` rule to handle vowel elision and tone assignment.

```
- ð-àŋàl    sheep[noun_class_sg=ð,noun_class_pl=unmarked,case=nom]
- ð-àŋàl-à  sheep[noun_class_sg=ð,noun_class_pl=unmarked,case=acc]
- j-àŋàl    sheep[noun_class_sg=unmarked,noun_class_pl=j,case=nom]
- j-àŋàl-à  sheep[noun_class_sg=unmarked,noun_class_pl=j,case=acc]

- ð-ɔ̀nd̪-à  gourd[noun_class_sg=ð,noun_class_pl=unmarked,case=nom]
- ð-ɔ̀nd̪-à  gourd[noun_class_sg=ð,noun_class_pl=unmarked,case=acc]
...
```

Thus we define a sequence `ClassPrefix-NounStem-CaseSuffix-HiatusResolution` which constructs a bijection between gloss+feature vector tuples.

Now briefly consider a sequence containing a `Paradigm`, for example `ArgumentMarker-VerbStem-FinalVowel`.
`ArgumentMarker` is a paradigm built from the `ArgumentPrefix` `Lexicon` object with `tam` and `deixis` as lexical features and `class` as an inflected feature.

```csv
root,tam,deixis
[CL]ə̀-,,pfv,ventive
[CL]à-,,pfv,itive
[CL]á-,,ipfv,ventive
[CL]á-,,ipfv,itive
```

The `ArgumentMarker` paradigm links a `FeatureMarker` definition which inflects the `class` feature, replacing the `[CL]` flag with the appropriate prefix, yielding bijections such as:

```
- j-ə̀-  [tam=pfv,deixis=ventive,class=j]
- ð-ə̀-  [tam=pfv,deixis=ventive,class=ð]
- l-ə̀-  [tam=pfv,deixis=ventive,class=l]

- j-à-  [tam=pfv,deixis=itive,class=j]
- ð-à-  [tam=pfv,deixis=itive,class=ð]
- l-à-  [tam=pfv,deixis=itive,class=l]

- j-á-  [tam=ipfv,deixis=ventive,class=j]
...
```

We also have `VerbStem`, which is built off the `VerbRoot` lexicon, which has lexical feature `finalvowel` and inflectional features `tam` and `deixis`:

```csv
root,gloss,finalvowel
vəlɛð,pull,aɔ
kɜc,take,ɔi
```

The `VerbStem` paradigm provides rules for exponing `tam` and `deixis`, yielding the following bijections:

```
- və̀lɛ̀ð pull[tam=perfective,deixis=ventive]
- və́lɛ̀ð pull[tam=perfective,deixis=itive]
- və̀lɛ̀ð pull[tam=imperfective,deixis=ventive]
- və́lɛ̀ð pull[tam=imperfective,deixis=itive]
```

Finally, `FinalVowel` is a `Lexicon` object with `tam`, `deixis` and `finalvowel` as lexical features:

```csv
root,finalvowel,tam,deixis
-à,aɔ,itive,imperfective
-ɔ́,aɔ,ventive,imperfective
-ɛ̀,aɔ,itive,perfective
-ɔ́,aɔ,ventive,perfective
-ɔ̀,ɔi,itive,imperfective
-í,ɔi,ventive,imperfective
-ì,ɔi,itive,perfective
-í,ɔi,ventive,perfective
```

Combining all three gives us bijections for fully inflected Tira verbs:

```
- j-ə̀-və̀lɛ̀ð-ɔ́   pull[tam=perfective,deixis=ventive,class=j,finalvowel=aɔ]
- l-ə̀-və̀lɛ̀ð-ɔ́   pull[tam=perfective,deixis=ventive,class=l,finalvowel=aɔ]

- j-á-və́lɛ̀ð-à   pull[tam=imperfective,deixis=ventive,class=j,finalvowel=aɔ]
- l-á-və́lɛ̀ð-à   pull[tam=imperfective,deixis=ventive,class=l,finalvowel=aɔ]

- j-ə̀-kɜ̀c-í     take[tam=perfective,deixis=ventive,class=j,finalvowel=ɔi]
- l-ə̀-kɜ̀c-í     take[tam=perfective,deixis=ventive,class=l,finalvowel=ɔi]
```

## YAML config

The YAML for the morpheme sequence is simple:

```yaml
kind: MorphemeSequence
data:
    - type: Lexicon
      value: $argument_prefix
    - type: Pattern
      value: "_"
    - type: Paradigm
      value: $regular_verb_stem
    - type: Lexicon
      value: $verb_final_vowel
    - type: Rule
      value: $vowel_hiatus_resolution
```

Where the `type` attr indicates the type of morpheme and `value` is either a reference to an existing file (for `Lexicon` and `Paradigm`), `Rule` class, `Pattern` class, or an inline `Pattern` string (note: no other types can be specified inline!)

## Python backend

A `MorphemeSequence` class requires a `ParadigmRegistry` to retrieve paradigms, `LexiconRegistry` to retrieve lexicons, and `FstOrchestrator` to retrieve patterns and rules and to compile pattern strings.
It loads a single config file, and, similar to a `Paradigm`, implements functions for querying a fully inflected sequence based on inflectional features.

Like the `Paradigm` class, `MorphemeSequence` constructs a bijection between feature set and inflected strings.
Constructing this bijection is more complicated for `MorphemeSequence` objects, however.
We now need to consider the possible set of lexical items at each stage of the sequence, rather than applying operations to a single set of lexical entries as `Paradigm` classes do.

This can be implemented straightforwardly by first defining the possible feature space (which may simply be the Cartesian product of all constituent features, or the user may pass in a `FeatureCombinations` config), and for each feature vector therein, iterating through the sequence of morphemes and retrieving the subset of strings which map to a proper subset of the feature vector (allowing `unmarked` to match any feature value).

## Graph construction

The `MorphemeSequence` graph will be formed by a simple concatenation of the graph of each item in the sequence.
To this end, we need a way of getting an acceptor over all roots matching a particular feature set for a `Lexicon` and `Paradigm` object.

The `Paradigm` class already implements an analysis -> surface string bijection with the `inflect/parse_graph` properties.
Namely `inflect_graph` is a transducer of `root[*features]` -> `inflected string`, and `parse_graph` is the inverse.
We can get a subgraph for all roots with a particular feature vector by inputing an acceptor of all roots to `Paradigm.inflect_subparadigm`.
Let's add a simple helper `Paradigm.get_subparadigm_inflect_graph` that wraps `inflect_subparadigm` but passing the all-roots FSA as the stem input.

For the `Lexicon` class, we need to create a new method `roots_to_analyses` which transduces a root to a root with a stringified vector of all of the root's lexical feature specifications, e.g. `àpɾí` -> `àpɾí[sg_class=j][pl_class=unmarked]`.
This method should have optional arguments allowing a feature set to be passed which constrains the roots that participate in the resulting graph.

Then for each unique feature vector on the possible set for a given `MorphemeSequence` class, build the sequence graph for that feature set by concatenating sequence items with the following algorithm:

- For a `Lexicon` item concatenate the output of `roots_to_analyses(feature_vector)`
- For a `Paradigm` item concatenate the output of `get_subparadigm_inflect_graph(feature_vector)`
- For a `Pattern` item simply concatenate the pattern acceptor
- For a `Rule` item simply compose the rule (or list of rules, if the type is `rule_sequence`)

## Implementation Plan & Notes

- [x] Create `MorphemeSequence` orchestrator + registry.
- [x] Hook into `Grammar` class.
- [x] Define JSON schema and update `ConfigWalker`.
- [X] Add `roots_to_analyses` to `Lexicon` class
- [X] Add `get_subparadigm_inflect_graph` to `Paradigm` class
- [X] Implement FST concatenation and feature intersection logic.
- [X] Add Streamlit UI page for `MorphemeSequence`.
