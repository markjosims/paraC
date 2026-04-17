# inventory
YAML files for defining phoneme and symbol inventories for the parser.
The inventory broadly consists *phones* (e.g. consonants and vowels, but also tones, suprasegmentals and diacritics) and *flags* (used only internally for e.g. marking an unfilled TBU or a slot in a morphological template).
Inventory datafiles conform to the following YAML schema:
```yaml
kind: Inventory
data:
    consonant: # name of phone category
        _ref: "<C>" # shorthand for referring to any element in the set
        stop: # name of sub-category
            _ref: "<STOP>"
            # indicate the kind of inventory set by using the 'phones' key
            _phones: [p, t, k, b, d, g]
    slot_flags:
        # indicate the kind of inventory set by using the 'flags' key
        _flags: ["[CLASS]", "[SUBJ]", "[FV]"]
    tone_flags:
        _flags: ["[TBU]", "[FLOAT]"]
```
Flags are automatically cleaned up when an FST is decoded into strings.

Note the following symbols are reserved:
- `<Phone>`: Any phone (non-flag) in the inventory.
- `<Flag>`: Any flag in the inventory.
- `<Sigma>`: Any item in the inventory, phone(me) or flag.
- `<Empty>`: No input or output, useful for deletion and insertion rules.
- `-`: Morpheme boundary
- `[BOS]`: Beginning of string
- `[EOS]`: End of string
- `*`: Kleene star (0 or more repetitions of the preceding element)
- `+`: Plus operator (1 or more repetitions of the preceding element)
- `?`: Optional operator (1 or 0 of the preceding element)
