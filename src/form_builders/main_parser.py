"""
Imports paradigms and other FSTs from `adjective_forms.py`,
`noun_forms.py`, `verb_forms.py` and `uninflected_forms.py`
and creates a main parser FST that combines them all.
"""

import pynini
from src.constants import FV_CLASSES
from src.form_builders.adjective_forms import get_adjective_paradigm
from src.form_builders.noun_forms import get_noun_paradigm
from src.form_builders.verb_forms import (
    get_verb_stem_paradigm, get_aux_paradigm,
    get_verb_paradigm_w_aux,
)
from src.form_builders.derived_verb_forms import get_paradigms_for_all_extensions
from src.form_builders.uninflected_forms import get_uninflected_word_fst
from src.cache_decorators import fst_cache
import os
from typing import *

@fst_cache(os.path.dirname(__file__))
def get_main_parser():
    verb_paradigms = []
    
    verb_paradigms.append(get_aux_paradigm())

    for fv_class in FV_CLASSES:
        fv_paradigm = get_verb_stem_paradigm(fv_class)
        verb_paradigms.append(fv_paradigm)
        verb_paradigms.append(get_verb_paradigm_w_aux(fv_paradigm))

    derived_verb_paradigms = get_paradigms_for_all_extensions()
    verb_paradigms.extend(derived_verb_paradigms.values())

    verb_lemmatizers = []
    verb_analyzers = []

    for paradigm in verb_paradigms:
        verb_lemmatizers.append(paradigm.lemmatizer)
        verb_analyzers.append(paradigm.analyzer)
    
    main_verb_lemmatizer = pynini.union(*verb_lemmatizers)
    main_verb_analyzer = pynini.union(*verb_analyzers)
    main_verb_lemmatizer.optimize()
    main_verb_analyzer.optimize()

def inflect_word(word, features) -> str:
    return 'foo'

def parse_word(word) -> list[Dict[str, str]]:
    return [{'foo': 'bar'}, {'baz': 'qux'}]