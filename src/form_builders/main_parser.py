"""
Imports paradigms and other FSTs from `adjective_forms.py`,
`noun_forms.py`, `verb_forms.py` and `uninflected_forms.py`
and creates a main parser FST that combines them all.
"""

import pynini
from pynini.lib import pynutil
from src.constants import FV_CLASSES
from src.form_builders.adjective_forms import get_adjective_paradigm
from src.form_builders.noun_forms import get_noun_paradigm
from src.form_builders.verb_forms import (
    get_verb_stem_paradigm, get_aux_paradigm,
    get_verb_paradigm_w_aux,
)
from src.fst_helpers import (
    fst, decode_fst_lattice, vectorize_feature_dict, vectorize_lexeme_string,
)
from src.form_builders.uninflected_forms import get_uninflected_word_fst
from src.cache_decorators import fst_cache
from src.lexicon import get_gloss_for_root
import os
from typing import *

def get_verb_paradigms():
    verb_paradigms = []
    verb_paradigms.append(get_aux_paradigm())

    for fv_class in FV_CLASSES:
        fv_paradigm = get_verb_stem_paradigm(fv_class)
        verb_paradigms.append(fv_paradigm)
        verb_paradigms.append(get_verb_paradigm_w_aux(fv_paradigm))

    return verb_paradigms

@fst_cache(os.path.dirname(__file__))
def get_main_parser() -> Tuple[pynini.Fst, pynini.Fst, pynini.Fst]:
    all_paradigms = get_verb_paradigms()
    all_paradigms.append(get_noun_paradigm())
    all_paradigms.append(get_adjective_paradigm())

    lemmatizers = []
    analyzers = []
    inflectors = []

    for paradigm in all_paradigms:
        lexical_flag_vector = vectorize_lexeme_string(paradigm.name)
        output_lexical_flags = pynutil.insert(lexical_flag_vector.acceptor)
        input_lexical_flags = pynutil.delete(lexical_flag_vector.acceptor)
        lemmatizers.append(paradigm.lemmatizer+output_lexical_flags)
        analyzers.append(paradigm.analyzer+output_lexical_flags)
        inflectors.append(paradigm.inflector+input_lexical_flags)

    # uninflected words have a single FST rather than a Paradigm object
    uninflected_word_fst = get_uninflected_word_fst()
    lemmatizers.append(uninflected_word_fst)
    analyzers.append(uninflected_word_fst)
    # there is no equivalent to "inflector" for uninflected words

    main_lemmatizer = pynini.union(*lemmatizers)
    main_analyzer = pynini.union(*analyzers)
    main_inflector = pynini.union(*inflectors)
    main_lemmatizer.optimize()
    main_analyzer.optimize()
    main_inflector.optimize()

    return main_lemmatizer, main_analyzer, main_inflector

def inflect_word(root, features) -> str:
    feature_vector, flag_vector = vectorize_feature_dict(features)
    _, _, main_inflector = get_main_parser()
    input_fst = fst(root) + feature_vector.acceptor + flag_vector.acceptor
    output_fst = input_fst @ main_inflector
    decoded_strs = decode_fst_lattice(output_fst, strings_only=True)
    return decoded_strs

def parse_word(word) -> list[Dict[str, str]]:
    main_lemmatizer, main_analyzer, _ = get_main_parser()
    input_fst = fst(word)
    lemmatized_lattice = input_fst @ main_lemmatizer
    parses = decode_fst_lattice(lemmatized_lattice)

    analyzed_lattice = input_fst @ main_analyzer
    analyses = decode_fst_lattice(analyzed_lattice)
    analyses = [analysis['form'] or analysis for analysis in analyses]
    
    for parse in parses:
        parse['analyzed_form'] = analyses
        pos = parse['pos']
        if pos not in ['verb', 'noun', 'adjective']:
            pos = 'uninflected'
        gloss = get_gloss_for_root(parse['root'], pos)
        parse['gloss'] = gloss

    return parses