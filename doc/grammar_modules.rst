```
prose: wip
media: not started
citations: not started
internal_links: not started
```

Grammar Modules
===============

Grammar modules are how Modopar defines the logic for constructing a morphological parser.
Modules are grouped into the following types: **phonology**, **exponence**, **lexicon**, and **morphotactics**.


Phonology
---------

Phonology modules in Modopar correspond roughly to the proper meaning of phonology in linguistics.
Modopar uses a generative rule-based framework for phonology.
Namely, underlying representations are transformed into surface forms by the application of an ordered series of rules.
The purpose of the phonology modules is to define what units underlying and surface strings may consist of, and how underlying representations are transformed into surface forms.
There are three phonology modules: :doc:`inventory`, :doc:`rules` and :doc:`patterns`.

Inventory
`````````

The Inventory module defines the possible **phones** and **symbols** that may make up the underlying and surface.
Here **phone** corresponds closest to the *surface alphabet* in Koskenniemi (!CITE).
It may be a phone proper (i.e. an IPA character indicating a phoneme or the surface realization of a phoneme) or a grapheme, depending on the user's preference and the indended usage of the parser.
Phones appear in both underlying and surface strings.
A **symbol** corresponds closest to an archiphoneme or morphophoneme, also following Koskenniemi (!CITE), or to a lexical diacritic in generative phonology (!CITE).
Symbols are restricted to underlying strings in Modopar, and are used to control the application of rules or morphological operations.
For example, the ``[TBU]`` symbol is used for Tira to indicate a tone-bearing unit whose tone has not yet been assigned.

Phones and symbols are grouped under **classes** in Modopar, where each class is indicated with a shorthand in angle brackets.
For example, we may use ``<C>`` as the shorthand referring to all consonants.
Classes may be also be nested.
For example, ``<C>`` may have a subclass ``<R>`` containing all resonant consonants.
The angle bracket shorthand may be used as a **pattern string** indicating any member of the class, as described in :doc:`patterns`.

Rules
`````

The Rules module allows the user to specify context-sensitive rewrite operations.
These correspond to operations in Sound Patterns of English (SPE) (!CITE)...
- Simple rule
- String map
- Rule sequence

Patterns
````````

The Patterns module allows the user to define shorthands...


Exponence
---------

Lexicon
-------

Morphotactics
-------------