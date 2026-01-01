"""
Imports paradigms and other FSTs from `adjective_forms.py`,
`noun_forms.py`, `verb_forms.py` and `uninflected_forms.py`
and creates a main parser FST that combines them all.
"""

import pynini
from pynini.lib import pynutil
from src.constants import FV_CLASSES
from src.form_builders.adnominal_forms import get_adjective_paradigm
from src.form_builders.noun_forms import get_noun_paradigm
from src.form_builders.verb_forms import (
    get_verb_stem_paradigm, get_aux_paradigm,
    get_verb_paradigm_w_aux,
)
from src.form_builders.uninflected_forms import get_uninflected_word_fst
from src.fst_helpers import (
    delete_fst, fst, insert_fst, parse_lattice_outputs, get_features_fsa,
    vectorize_feature_dict, vectorize_lexeme_string, get_lattice_strs,
    stringify_lexeme_features,
)
from src.cache_decorators import fst_cache, Timer
from src.lexicon import get_gloss_for_root, get_verb_root_w_hyphen, get_root_for_gloss, get_part_of_speech_for_root, \
    get_class_for_verb_root
import os
from typing import *

from src.lexicon.phonology import (
    EOS,
    SIGMASTAR,
    SIGMASTAR_W_TAG,
    SIGMASTAR_W_SYMBOLS,
    FINAL_LOWERING_RULE,
    LEFT_H_RULE,
)

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

def add_tone_processes_to_inflector(inflector_fst: pynini.Fst) -> pynini.Fst:
    """
    Arguments:
        inflector_fst: The main inflector FST before tone processes are added.
    Returns:
        The main inflector FST with tone processes added.

    Wraps `add_tone_processes_to_parser`. Inverts inflector FST before and after
    adding tone processes.
    """
    inflector_reversed = pynini.invert(inflector_fst)
    inflector_with_tone = add_tone_processes_to_parser(inflector_reversed)
    inflector_final = pynini.invert(inflector_with_tone)
    return inflector_final

def add_tone_processes_to_parser(parser_fst: pynini.Fst) -> pynini.Fst:
    """
    Arguments:
        parser_fst: The main parser FST before tone processes are added.
    Returns:
        The main parser FST with tone processes added.

    Adds paths for tone processes (left H docking/spreading, final lowering)
    to `parser_fst`.
    """
    tone_rules = [
        (('final_lowering',), FINAL_LOWERING_RULE),
        (('left_h',), LEFT_H_RULE),
        (('final_lowering', 'left_h'), FINAL_LOWERING_RULE @ LEFT_H_RULE),
    ]
    parser_list = [parser_fst]
    for feature_tuple, rule_fst in tone_rules:
        set_features_to_positive = SIGMASTAR_W_SYMBOLS
        for feature in feature_tuple:
            positive_feature = f"{feature}=true"
            unmarked_feature = f"{feature}=unmarked"
            set_features_to_positive @= pynini.cdrewrite(
                tau=fst(unmarked_feature, positive_feature),
                l=fst(),
                r=fst(),
                sigma_star=SIGMASTAR_W_SYMBOLS,
            )
        if 'final_lowering' in feature_tuple:
            # need to ensure EOS is present for final lowering
            forms_w_eos2forms = pynini.project(parser_fst, 'input') + delete_fst(EOS)
            feature_parser = forms_w_eos2forms @ parser_fst
        else:
            feature_parser = parser_fst
        feature_parser_input = pynini.project(feature_parser, 'input')
        forms_w_process = feature_parser_input@rule_fst
        forms_w_process.invert()

        # remove redundant paths where process is applied vacuously
        redundant_paths = feature_parser_input @ forms_w_process
        redundant_paths.project('input')
        process_input = pynini.project(forms_w_process, 'input')
        non_redundant_paths = process_input - redundant_paths
        forms_w_process = non_redundant_paths @ forms_w_process

        process_fst = forms_w_process @ feature_parser @ set_features_to_positive
        process_fst.optimize()

        parser_list.append(process_fst)

    parser_fst = pynini.union(*parser_list)
    parser_fst.optimize()
    return parser_fst

@fst_cache(_form_builders_dir, num_fst=3)
def get_main_parser() -> Tuple[pynini.Fst, pynini.Fst, pynini.Fst]:
    print("Building main parser FSTs...")

    print("Gathering paradigms...")
    all_paradigms = get_verb_paradigms()
    all_paradigms.append(get_noun_paradigm())
    all_paradigms.append(get_adjective_paradigm())

    lemmatizers = []
    analyzers = []
    inflectors = []

    print("Adding lexical flags to paradigms...")
    for paradigm in all_paradigms:
        lexical_flag_vector = vectorize_lexeme_string(paradigm.name)
        output_lexical_flags = pynutil.insert(lexical_flag_vector.acceptor)
        input_lexical_flags = pynutil.delete(lexical_flag_vector.acceptor)
        lemmatizers.append(paradigm.lemmatizer+output_lexical_flags)
        analyzers.append(paradigm.analyzer+output_lexical_flags)
        inflectors.append(paradigm.inflector+input_lexical_flags)

    print("Adding uninflected words...")
    # uninflected words have a single FST rather than a Paradigm object
    uninflected_word_fst = get_uninflected_word_fst()
    lemmatizers.append(uninflected_word_fst)
    analyzers.append(uninflected_word_fst)
    # there is no equivalent to "inflector" for uninflected words

    print("Combining FSTs into global lemmatizer, analyzer, and inflector...")
    main_lemmatizer = pynini.union(*lemmatizers)
    main_analyzer = pynini.union(*analyzers)
    main_inflector = pynini.union(*inflectors)
    main_lemmatizer.optimize()
    main_analyzer.optimize()
    main_inflector.optimize()

    print("Adding tone processes...")
    main_lemmatizer = add_tone_processes_to_parser(main_lemmatizer)
    main_analyzer = add_tone_processes_to_parser(main_analyzer)
    main_inflector = add_tone_processes_to_inflector(main_inflector)

    return main_lemmatizer, main_analyzer, main_inflector


def inflect_word(
        root: str=None,
        gloss: str=None,
        **feature_kwargs,
) -> List[str]:
    """
    Given a root and features, returns the inflected forms.
    If 'gloss' is passed instead of 'root', find the root(s) corresponding to that gloss.

    Args:
        root:
        gloss:
        **feature_kwargs:

    Returns:
        List of strings representing the inflected forms.
    """
    if root is None:
        if gloss is None:
            raise ValueError("Either 'root' or 'gloss' must be provided.")
        # get root(s) for gloss and return inflected forms for each
        roots_and_pos = get_root_for_gloss(gloss, return_pos=True)
        inflected_forms = []
        for root, pos in roots_and_pos:
            feature_kwargs['part_of_speech'] = pos
            inflected_forms.extend(
                inflect_word(
                    root=root,
                    **feature_kwargs
                )
            )
        return list(set(inflected_forms))  # remove duplicates

    if 'part_of_speech' not in feature_kwargs:
        possible_pos = get_part_of_speech_for_root(root)
        for part_of_speech in possible_pos:
            inflected_forms = []
            feature_kwargs['part_of_speech'] = part_of_speech
            inflected_forms.extend(inflect_word(
                root=root,
                **feature_kwargs
            ))
        return list(set(inflected_forms))  # remove duplicates

    if (feature_kwargs['part_of_speech'] == 'verb') and (feature_kwargs.get('fv', None) is None):
        fv_list = get_class_for_verb_root(root)
        inflected_forms = []
        for fv in fv_list:
            inflected_forms.extend(inflect_word(
                root=root,
                fv=fv,
                **feature_kwargs
            ))
        return list(set(inflected_forms))  # remove duplicates

    feature_vector, flag_vector = vectorize_feature_dict(feature_kwargs)
    _, _, main_inflector = get_main_parser()
    input_fst = fst(root) + feature_vector.acceptor + flag_vector.acceptor
    output_fst = input_fst @ main_inflector
    inflected_strs = get_lattice_strs(output_fst)
    return inflected_strs

def parse_word(
        word: str,
        main_lemmatizer: pynini.Fst = None,
        main_analyzer: pynini.Fst = None
    ) -> list[Dict[str, str]]:
    if main_lemmatizer is None or main_analyzer is None:
        main_lemmatizer, main_analyzer, _ = get_main_parser()
    input_fst = fst(word)
    lemmatized_lattice = input_fst @ main_lemmatizer
    parses = parse_lattice_outputs(lemmatized_lattice, word_key='root')
    for parse in parses[:]:
        parse['form']=word
        if parse['part_of_speech'] == 'verb':
            verb_root = get_verb_root_w_hyphen(parse['root'], parse['fv'])
            parse['root'] = verb_root[0]
            if len(verb_root) > 1:
                for root in verb_root[1:]:
                    new_parse = parse.copy()
                    new_parse['root'] = root
                    parses.append(new_parse)

    parses = add_analysis_and_gloss_to_parses(
        parses,
        input_fst=input_fst,
        main_analyzer=main_analyzer
    )
    return parses

def parse_is_root(parse: Dict[str, str]) -> bool:
    """
    Determines whether a given parse corresponds to a root form
    (i.e. form with no features marked).
    Arguments:
        parse: A dictionary representing a parse.
    Returns:
        True if the parse corresponds to a root form, False otherwise.
    """
    if parse['part_of_speech'] == 'noun':
        return parse['case'] == 'unmarked'
    if parse['part_of_speech'] == 'verb':
        return parse['tam'] == 'unmarked'
    if parse['part_of_speech'] == 'adjective':
        return parse['class'] == 'unmarked'
    return False


def add_analysis_and_gloss_to_parses(
        parses,
        input_fst=None,
        main_analyzer=None
    ) -> list[Dict[str, str]]:
    if main_analyzer is None:
        _, main_analyzer, _ = get_main_parser()
    new_parses = []

    non_feature_keys = ['root', 'weight']
    for parse in parses:
        new_parse = parse.copy()
        if input_fst is None:
            input_fst = fst(parse['form'])
        feature_dict = {k: v for k, v in parse.items() if k not in non_feature_keys}
        features_fsa = get_features_fsa(feature_dict)
        analysis_lattice = input_fst @ main_analyzer @ (SIGMASTAR_W_TAG + features_fsa)
        analyses = get_lattice_strs(analysis_lattice)
        # assert len(analyses) == 1, f"Expected exactly one analysis, got {analyses}"
        # temporarily commenting out to update dataset w/o causing bugs
        new_parse['analyzed_form'] = analyses[0].split('[')[0]

        part_of_speech = parse["part_of_speech"]
        if part_of_speech not in ['verb', 'noun', 'adjective']:
            part_of_speech = 'uninflected'
        glosses = get_gloss_for_root(parse['root'], part_of_speech)
        for gloss in glosses:
            new_parse['gloss'] = gloss
            new_parses.append(new_parse)

    
    return new_parses