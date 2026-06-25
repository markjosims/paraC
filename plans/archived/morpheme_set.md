# Morpheme Set

A set of affixes or clitics exponing inflectional features.

## Config file

```yaml
kind: MorphemeSet
features:
    - person
    - number
data:
    - morpheme: "-o"
      features:
        person: "1"
        number: "sg"
    - morpheme: "-as"
      features:
        person: "2"
        number: "pl"  
    ...
```

## Python backend

`MorphemeSet` class loads a config file following the logic of `ContingentMarkers` (but simpler since there are no global markers or inheritance).
`MorphemeSetRegistry` is a simple aggregator of `MorphemeSet` classes.

## Streamlit frontend

`Morpheme Set` editor page should follow `ContingentMarkers` page closely save the morphemes are entered as a simple string rather than as a marker.

## Plan & Implementation

- [x] JSON schema
- [x] `MorphemeSet` class
- [x] `MorphemeSetRegistry` class
- [x] `Morpheme Set` editor
