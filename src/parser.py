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
from src.form_builders.uninflected_forms import get_uninflected_word_fst
from src.fst_helpers import (
    fst, parse_lattice_outputs, get_features_fsa,
    vectorize_feature_dict, vectorize_lexeme_string, get_lattice_strs,
    stringify_lexeme_features,
)
from src.cache_decorators import fst_cache
from src.lexicon import get_gloss_for_root, get_verb_root_w_hyphen
import os
from typing import *

from src.lexicon.phonology import SIGMASTAR_W_TAG

__dir__ = os.path.dirname(os.path.abspath(__file__))
_form_builders_dir = os.path.join(__dir__, 'form_builders')

def get_verb_paradigms():
    verb_paradigms = []
    verb_paradigms.append(get_aux_paradigm())

    for fv_class in FV_CLASSES:
        fv_paradigm = get_verb_stem_paradigm(fv_class)
        verb_paradigms.append(fv_paradigm)
        verb_paradigms.append(get_verb_paradigm_w_aux(fv_paradigm))

    return verb_paradigms

@fst_cache(_form_builders_dir, num_fst=3)
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


def inflect_word(root, feature_dict) -> List[Tuple[str, float]]:
    feature_vector, flag_vector = vectorize_feature_dict(feature_dict)
    _, _, main_inflector = get_main_parser()
    input_fst = fst(root) + feature_vector.acceptor + flag_vector.acceptor
    output_fst = input_fst @ main_inflector
    inflected_strs = get_lattice_strs(output_fst)
    return inflected_strs

def parse_word(word) -> list[Dict[str, str]]:
    main_lemmatizer, _, _ = get_main_parser()
    input_fst = fst(word)
    lemmatized_lattice = input_fst @ main_lemmatizer
    parses = parse_lattice_outputs(lemmatized_lattice, word_key='root')
    for parse in parses:
        parse['form']=word
        if parse['part_of_speech'] == 'verb':
            parse['root'] = get_verb_root_w_hyphen(parse['root'])
    parses = add_analysis_and_gloss_to_parses(parses, input_fst=input_fst)

    return parses

def add_analysis_and_gloss_to_parses(parses, input_fst=None) -> list[Dict[str, str]]:
    _, main_analyzer, _ = get_main_parser()

    non_feature_keys = ['root', 'weight']
    for parse in parses:
        if input_fst is None:
            input_fst = fst(parse['form'])
        feature_dict = {k: v for k, v in parse.items() if k not in non_feature_keys}
        features_fsa = get_features_fsa(feature_dict)
        analysis_lattice = input_fst @ main_analyzer @ (SIGMASTAR_W_TAG + features_fsa)
        analyses = get_lattice_strs(analysis_lattice)
        assert len(analyses) == 1, f"Expected exactly one analysis, got {analyses}"
        parse['analyzed_form'] = analyses[0].split('[')[0]

        pos = parse["part_of_speech"]
        if pos not in ['verb', 'noun', 'adjective']:
            pos = 'uninflected'
        gloss = get_gloss_for_root(parse['root'], pos)
        parse['gloss'] = gloss
    
    return parses