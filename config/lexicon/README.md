# lexicon
CSV files for storing lexical data, where each file gives data for a single part of speech.
Each CSV must have a corresponding YAML file under config/parts_of_speech specifying metadata.
E.g. `data/lexicon/noun.csv` must have an associated `config/parts_of_speech/noun.yaml`.
See the [parts of speech documentation](config/parts_of_speech/README.md) for more information.

The CSV file must contain at minimum the columns 'root' and 'gloss', e.g.:
```csv
root,gloss
perro,dog
gato,cat
mujer,woman
hombre,man
```

More lexical and grammatical information can be specified with the addition of optional columns, as described in the remainder of this document.

## Lexical classes
Different from flags because they're used for filtering, not for reference in rules...

## Lexical flags
Lexical flags control the logic for a particular root.
Must have angle brackets...

```csv
root,gloss,stem_pattern
tener,have,<ng_and_diphthong>
venir,come,<ng_and_diphthong>
conocer,know,<c_zc_alternation>

## Principal parts
Adding columns for various principal parts...
```csv
root,gloss,past_stem
hablar,speak,
estar,be,estuv
hacer,do,hic
traer,bring,traj
```