# patterns
A pattern is a Finite State Acceptor (FSA) describing a language of strings that can be used as part of the input or output of a [rule](config/rules/README.md).
Patterns are YAML dictionaries that consist of two keys, 'pattern' and 'ref'.
The 'pattern' attribute is a single string which is essentially a regular expression describing some natural class or recurring phoneme sequence that is useful for describing morphological operations in a given language.
The 'ref' attribute, as is the case for classes in [Inventory](config/inventory/README.md) objects, is a unique string that can be used to refer to the pattern.
Like `Inventory` classes, the 'ref' string must be surrounded by angle braces.
```yaml
kind: Patterns
patterns:
    - non_high_vowel:
        pattern: "(<V_Low>|<V_Mid>)"
        ref: "<V_NonHigh>"
    - voiced_stop:
        pattern: [b, d, g]
        ref: <VcdStop>
```
Patterns can be used to build other patterns by using the 'ref' value:
```yaml
kind: Patterns
pattern:
    - tone_bearing_segment:
        pattern: "(<M>|<R>|<V>)"
        # using <TBU_SEG> rather than [TBU] to avoid confusion with the [TBU] tag
        ref: "<TBU_SEG>"
    - syllable:
        pattern: "<C>?<TBU_SEG><C>?"
        ref: "<Syll>"
```
Patterns can reference patterns defined earlier in the same document or in another document provided that document does not itself reference the current, to prevent circular imports.