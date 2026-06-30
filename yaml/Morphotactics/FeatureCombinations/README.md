# FeatureCombinations
It is often the case that not all possible feature combinations are grammatical in a language.
For example, imperatives can only be marked for second person singular and second person plural in Spanish.
To enforce this restriction, we can define a `FeatureCombinations` config which specifies what sets of features are permissible in the language.
This config has two required keys: 'features' and 'combinations',
where 'features' enumerates all features used and 'combinations' is a list of dictionaries describing various possible ways the given features can co-occur.
Each element of 'combinations' has the names of features as keys, and the values are the possible values features can take on for that set of combinations, or the wildcard operator "*" to indicate all features.
For example, the config below says that the indicative and subjunctive may combine with any person or tense, but that the imperative can only occur with present tense and 2sg or 2pl.
If any feature is left out it is assumed to be unmarked.
For example the infinitive mood here is assumed to have unmarked person and tense.
```yaml
kind: FeatureCombinations
features:
  - person
  - tense
  - mood
combinations:
  - person: "*"
    tense: "*"
    mood: [indicative, subjunctive]
  - person: ["2sg", "2pl"]
    tense: present
    mood: imperative
  - mood: infinitive
```
Feature combinations are used by `Paradigm` configs to define the slots built by that paradigm.
See the [paradigm documentation](config/paradigms/README.md) for more information.