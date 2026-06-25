# Inflection

## Backend

Add `inflect` and `get_inflection_stages` to `MorphemeSequence` class in [morpheme_sequence_registry.py](../src/grammar/registry/morpheme_sequence_registry.py) based off [paradigm_registry.py](../src/grammar/registry/paradigm_registry.py).
Unlike `Paradigm` which takes a single stem, `MorphemeSequence` will need to take a list of stems: one for each `Lexicon` or `Paradigm` in the sequence.
For `get_inflection_stages`, each step should get at least one stage (illustrating to the output of that `step_fst`), then for `Paradigm` steps extend by the `Paradigm.get_inflection_stages` method.

## Frontend

Add a page "Inflector" modeled after the [Flask page](../deprecated/web/routes.py) and [HTML template](../deprecated/web/templates/_inflect_stages.html).
Write code to [inflector.py](../src/pages/inflector.py).
It should allow the user to input a stem (for paradigms) or list of stems (for morpheme sequences) and print out the inflection stages.
