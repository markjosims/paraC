Grammar Modules
===============

Grammar modules are how Modopar defines the logic for constructing a morphological parser.
Modules are grouped into the following types: **phonology**, **exponence**, **lexicon**, and **morphotactics**.


Phonology
---------

"Phonology" modules in Modopar correspond roughly to the proper meaning of phonology in linguistics, with a few practical differences.
There are three phonology modules: :doc:`inventory`, :doc:`rules` and :doc:`patterns`.

Inventory
`````````

To build a morphological parser, we first need to define what are the possible input characters for that parser.
An English parser, for example, should not accept a Chinese character such as 中... (something about IPA vs orthography?)

The Inventory module defines the possible **phones** and **symbols** that may be input to the parser.
Since the user may wish to construct a parser that employs underlying phonological representations, surface-level phonetic representations or a practical orthography, "phones" here may correspond to phonemes, allophones, or graphemes.
Symbols have a more specific and user-defined purpose.
A symbol is...

Exponence
---------

Lexicon
-------

Morphotactics
-------------