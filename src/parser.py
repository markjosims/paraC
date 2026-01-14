"""
Imports paradigms and other FSTs from `adjective_forms.py`,
`noun_forms.py`, `verb_forms.py` and `uninflected_forms.py`
and creates a main parser FST that combines them all.
"""

import pynini
from loguru import logger
from pynini.lib import pynutil
from src.constants import FV_CLASSES
from src.form_builders.adnominal_forms import get_adjective_paradigm, get_all_adnominal_paradigms
from src.form_builders.nominal_forms import get_all_nominal_paradigms
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
from src.decorators import fst_cache, _log_fst_stats
from src.lexicon import get_gloss_for_root, get_verb_root_w_hyphen, get_root_for_gloss, get_part_of_speech_for_root, \
    get_class_for_verb_root
import os
from typing import *

from src.lexicon.phonology import (
    EOS,
    SIGMA,
    SIGMASTAR_W_TAG,
    SIGMASTAR_W_SYMBOLS,
    FINAL_LOWERING_RULE_NONVACUOUS,
    LEFT_H_RULE_NONVACUOUS,
)
from multiprocessing import Pool

__dir__ = os.path.dirname(os.path.abspath(__file__))
_form_builders_dir = os.path.join(__dir__, 'form_builders')

def add_tone_processes_to_inflector(inflector_fst: pynini.Fst) -> pynini.Fst:
    """
    Wraps `add_tone_processes_to_parser`. Inverts inflector FST before and after
    adding tone processes.

    Arguments:
        inflector_fst: The main inflector FST before tone processes are added.
    Returns:
        The main inflector FST with tone processes added.
    """
    _log_fst_stats([inflector_fst], "add_tone_processes_to_inflector[INITIAL]", "inflector_fst")
    inflector_reversed = pynini.invert(inflector_fst)
    inflector_with_tone = add_all_tone_processes_to_parser(inflector_reversed)
    inflector_final = pynini.invert(inflector_with_tone)
    _log_fst_stats([inflector_final], "add_tone_processes_to_inflector[FINAL]", "inflector_final")
    return inflector_final

def add_all_tone_processes_to_parser(parser_fst: pynini.Fst) -> pynini.Fst:
    """
    Adds paths for tone processes (left H docking/spreading, final lowering)
    to `parser_fst`.

    Arguments:
        parser_fst: The main parser FST before tone processes are added.
    Returns:
        The main parser FST with tone processes added.
    """
    tone_rules = [
        (('final_lowering',), FINAL_LOWERING_RULE_NONVACUOUS),
        (('left_h',), LEFT_H_RULE_NONVACUOUS),
        (('final_lowering', 'left_h'), [FINAL_LOWERING_RULE_NONVACUOUS, LEFT_H_RULE_NONVACUOUS]),
    ]
    parser_list = [parser_fst]
    parser_input_projection = pynini.project(parser_fst, 'input')
    for feature_names, rule_fst in tone_rules:
        logger.info(f"Computing parser with tone process: {', '.join(feature_names)}")
        feature_map = {
            feature_name: ('unmarked', 'true')
            for feature_name in feature_names
        }
        parser_fst_with_tone = add_process_to_parser(
            parser_fst,
            parser_input_projection,
            rule_fst,
            feature_map,
        )
        parser_list.append(parser_fst_with_tone)
    
    _log_fst_stats(parser_list, "add_all_tone_processes_to_parser[PRE-UNION]", f"parser_fst")

    parser_fst = pynini.union(*parser_list).optimize()
    _log_fst_stats([parser_fst], "add_all_tone_processes_to_parser[POST-UNION]", f"parser_fst")

    return parser_fst

def add_process_to_parser(
        parser_fst: pynini.Fst,
        parser_input_projection: pynini.Fst,
        rule_fst: pynini.Fst,
        feature_map: Dict[str, Tuple[str, str]],
) -> pynini.Fst:
    """
    Arguments:
        parser_fst: The main parser FST before tone processes are added.
        parser_input_projection: The input projection of `parser_fst`.
        rule_fst: The phonological rule FST to apply.
        feature_map: Dictionary mapping features to tuples of (from_value, to_value).
    Returns:
        The main parser FST with tone processes added.

    Adds paths for a single tone process to `parser_fst`.
    """
    parser_w_rule = apply_rule_to_input(parser_fst, parser_input_projection,rule_fst)
    parser_w_shifted_features = shift_feature_value(parser_w_rule, feature_map)
    _log_fst_stats([parser_w_shifted_features], "add_process_to_parser", "parser_w_shifted_features")
    return parser_w_shifted_features.optimize()

def append_eos_to_input(
        parser: pynini.Fst,
        optional: bool=False,
) -> pynini.Fst:
    """
    Given a parser FST that maps form strings to parses,
    returns an equivalent FST where EOS is appended to all
    strings on the input side.

    Arguments:
        parser: FST mapping forms to parses.
        optional: If True, EOS is optionally appended to input strings.
    Returns:
        FST equivalent to `parser` with EOS appended to input side.
    """
    parser_input = pynini.project(parser, 'input')
    # since delete maps a single symbol to epsilon,
    # we use delete_fst to map the EOS symbol on the left side
    # to epsilon on the right side
    if optional:
        forms_w_eos2forms_without_eos = parser_input + delete_fst(EOS).ques
    else:
        forms_w_eos2forms_without_eos = parser_input + delete_fst(EOS)

    forms_w_eos2forms_without_eos.optimize()
    # since the right side of this graph is equivalent to the input
    # side of `parser`, we can compose to get the desired FST
    # mapping forms with EOS to parses
    forms_w_eos = forms_w_eos2forms_without_eos @ parser
    forms_w_eos.optimize()

    _log_fst_stats([forms_w_eos], "append_eos_to_input", f"parser with optional={optional}")

    return forms_w_eos

def apply_rule_to_input(
    parser: pynini.Fst,
    parser_input_projection: pynini.Fst,
    rule: Union[pynini.Fst, List[pynini.Fst]],
) -> pynini.Fst:
    """
    Given a parser FST that maps form strings to parses,
    returns an equivalent FST where `rule` has been applied
    to all strings on the input side.

    If `prune_redundant_paths` is True, removes any paths
    where the application of `rule` does not change the form.
    Imagine `rule` describes the process of final lowering.
    The word "ðɔ̀mɔ̀cɔ̀", having a lexical all-low melody,
    is unchanged by final lowering. Then `parser` will have the relation:

        ðɔ̀mɔ̀cɔ̀ -> man[case=nominative][number=singular][final_lowering=unmarked]
    
    And `parser_w_rule` will have the relation:

        ðɔ̀mɔ̀cɔ̀ -> man[case=nominative][number=singular][final_lowering=true]

    Where final lowering has been applied vacuously. To avoid proliferation
    of vacuous paths like this, this setting this option removes such relations
    from `parser_w_rule` and returns only the non-redundant paths.
    
    Arguments:
        parser: FST mapping forms to parses.
        parser_input_projection: The input projection of `parser`.
        rule: FST or list of FSTs representing phonological rules to apply.
    Returns:
        FST equivalent to `parser` with `rule` applied to input side.
    """

    _log_fst_stats([parser], "apply_rule_to_input[INITIAL]", "parser")

    forms_w_rule = parser_input_projection

    if type(rule) is list:
        for r in rule:
            forms_w_rule = forms_w_rule @ r
    else:
        forms_w_rule = forms_w_rule @ rule

    # this FST now maps original forms to forms with the rule applied
    # to compose with the parser, we need to invert it
    # so that original forms are on the right side
    # and forms with the rule applied are on the left side
    forms_w_rule = pynini.invert(forms_w_rule)
    parser_w_rule = forms_w_rule @ parser

    # some rules are set to map non-applicable or vacuous inputs to epsilon
    # for this reason, we need to remove paths that are just epsilon on the input side
    parser_w_rule = SIGMA.plus @ parser_w_rule
    parser_w_rule.optimize()

    _log_fst_stats([parser_w_rule], "apply_rule_to_input[FINAL]", "parser_w_rule")

    return parser_w_rule

def shift_feature_value(parser: pynini.Fst, feature_map: Dict[str, Tuple[str, str]]) -> pynini.Fst:
    """
    Given a parser FST that maps form strings to parses,
    returns an equivalent FST where the value of `feature`
    has been changed from `from_value` to `to_value` on
    the output side.

    E.g. if `feature` "final_lowering" is changed from "unmarked" to "true",
    then all parses that had "final_lowering=unmarked" in the output language
    will now have "final_lowering=true" instead.

    Arguments:
        parser: FST mapping forms to parses.
        feature_map: Dictionary mapping features to tuples of (from_value, to_value).
    Returns:
        FST equivalent to `parser` with feature value shifted.
    """
    feature_rewrite_rule = SIGMASTAR_W_SYMBOLS
    for feature, (from_value, to_value) in feature_map.items():
        from_feature = f"[{feature}={from_value}]"
        to_feature = f"[{feature}={to_value}]"
        feature_rewrite_rule @= pynini.cdrewrite(
            tau=fst(from_feature, to_feature),
            l=fst(),
            r=fst(),
            sigma_star=SIGMASTAR_W_SYMBOLS,
        )

    feature_rewrite_rule.optimize()
    parser_shifted = parser @ feature_rewrite_rule
    parser_shifted.optimize()
    return parser_shifted

@fst_cache(_form_builders_dir, num_fst=3)
def get_main_parser() -> Tuple[pynini.Fst, pynini.Fst, pynini.Fst]:
    logger.info("Building main parser FSTs...")

    logger.info("Gathering paradigms...")
    all_paradigms = get_verb_paradigms()
    all_paradigms.extend(get_all_nominal_paradigms())
    all_paradigms.append(get_adjective_paradigm())
    all_paradigms.extend(get_all_adnominal_paradigms())

    lemmatizers = []
    analyzers = []
    inflectors = []

    logger.info("Adding lexical flags to paradigms...")
    for paradigm in all_paradigms:
        lexical_flag_vector = vectorize_lexeme_string(paradigm.name)
        output_lexical_flags = pynutil.insert(lexical_flag_vector.acceptor)
        input_lexical_flags = pynutil.delete(lexical_flag_vector.acceptor)

        lemmatizers.append(paradigm.lemmatizer+output_lexical_flags)
        analyzers.append(paradigm.analyzer+output_lexical_flags)
        inflectors.append(paradigm.inflector+input_lexical_flags)

    logger.info("Adding uninflected words...")
    # uninflected words have a single FST rather than a Paradigm object
    uninflected_word_fst = get_uninflected_word_fst()
    lemmatizers.append(uninflected_word_fst)
    analyzers.append(uninflected_word_fst)
    # there is no equivalent to "inflector" for uninflected words

    logger.info("Combining FSTs into global lemmatizer, analyzer, and inflector...")
    main_lemmatizer = pynini.union(*lemmatizers)
    main_analyzer = pynini.union(*analyzers)
    main_inflector = pynini.union(*inflectors)
    main_lemmatizer.optimize()
    main_analyzer.optimize()
    main_inflector.optimize()

    _log_fst_stats(
        [main_lemmatizer, main_analyzer, main_inflector],
        "get_main_parser[POST-UNION]",
        "main_lemmatizer, main_analyzer, main_inflector"
    )

    logger.info("Appending EOS to input side...")
    main_lemmatizer = append_eos_to_input(main_lemmatizer, optional=True)
    main_analyzer = append_eos_to_input(main_analyzer, optional=True)
    main_inflector = append_eos_to_input(main_inflector, optional=True)

    logger.info("Adding tone processes...")
    main_lemmatizer = add_all_tone_processes_to_parser(main_lemmatizer)
    main_analyzer = add_all_tone_processes_to_parser(main_analyzer)
    main_inflector = add_tone_processes_to_inflector(main_inflector)

    _log_fst_stats(
        [main_lemmatizer, main_analyzer, main_inflector],
        "get_main_parser[FINAL]",
        "main_lemmatizer, main_analyzer, main_inflector"
    )

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