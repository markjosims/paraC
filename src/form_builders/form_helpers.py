"""
Helper functions for creating paradigm functions
for various parts of speech.
"""

from typing import *
from src.fst_helpers import fst, decode_feature_label_rewriter
from src.constants import CLASS_PREFIXES, HIGH_TONE, LOW_TONE
from src.lexicon.phonology import DELETE_SCHWA_BEFORE_VOWEL, SIGMASTAR, REMOVE_DOUBLE_BOUNDARIES
import pynini
from pynini.lib import features, paradigms, rewrite
import pandas as pd

def prefix(
        fst_input: Union[str, Sequence[str], pynini.Fst],
        stem: Union[str, pynini.Fst, None] = None,
        weight: pynini.WeightLike = None,
    ) -> pynini.Fst:
    """
    Arguments:
        fst_input:  (Optional) string or list of strings to be accepted by the FST
        stem:       (Optional) string or FST to be used as the stem
        weight:     (Optional) weight value for FST
    Returns:
        f:          FST prefixing the input string(s)
    """
    if stem is None:
        stem = SIGMASTAR
    input_fsa = fst(fst_input=fst_input, weight=weight)
    return paradigms.prefix(input_fsa, stem)

def suffix(
        fst_input: Union[str, Sequence[str], pynini.Fst],
        stem: Union[str, pynini.Fst, None] = None,
        weight: pynini.WeightLike = None,
    ) -> Callable[[pynini.Fst], pynini.Fst]:
    """
    Arguments:
        fst_input:  (Optional) string or list of strings to be accepted by the FST
        stem:       (Optional) string or FST to be used as the stem.
                    If None, defaults to SIGMASTAR.
        weight:     (Optional) weight value for FST
    Returns:
        f:          FST suffixing the input string(s)
    """
    if stem is None:
        stem = SIGMASTAR
    input_fsa = fst(fst_input=fst_input, weight=weight)
    return paradigms.suffix(input_fsa, stem)


def add_class_prefix(stem: pynini.Fst, class_agree: str, prefix_tone=LOW_TONE) -> pynini.Fst:
    """
    Arguments:
        stem:           FST describing the stem to which the class prefix should be added
        class_agree:    the noun class to which the prefix should agree
        prefix_tone:    the tone of the prefix (default: low tone)
    Returns:
        An FST describing the stem with the appropriate class prefix added.
    """
    if class_agree == 'g':
        # 'g' class phonetically realized as [k]
        class_agree = 'k'
    prefix_acceptor = fst(f"{class_agree}ə{prefix_tone}-")
    return (paradigms.prefix(prefix_acceptor, stem)@REMOVE_DOUBLE_BOUNDARIES@DELETE_SCHWA_BEFORE_VOWEL).optimize()


def add_class_prefixes_to_slots(slot_list, include_ng:bool=False):
    """
    Arguments:
        slot_list:  A list of (stem, feature_vector) tuples
    Returns:
        A list of (stem_with_class_prefix, feature_vector_with_class) tuples
        for each class prefix in CLASS_PREFIXES.
    """
    slots_w_class_prefixes = []
    prefixes = CLASS_PREFIXES
    if include_ng:
        prefixes.append('ŋg')
    for stem, feature_vector in slot_list:
        category = feature_vector.category
        feature_dict = feature_vector.values.copy()
        feature_dict.pop('class', None)  # remove any existing class feature
        feature_values = [f"{feature}={value}" for feature, value in feature_dict.items()]
        for class_agree in CLASS_PREFIXES:
            prefix = class_agree
            if class_agree == 'ŋg':
                class_agree = 'g'
            features_with_class = features.FeatureVector(category, f"class={class_agree}", *feature_values)
            prefixed_verb = add_class_prefix(stem, prefix)
            slots_w_class_prefixes.append((prefixed_verb, features_with_class))
    return slots_w_class_prefixes


def generate_forms(
        stem: str,
        paradigm: paradigms.Paradigm,
        save_to_tmp: bool=False,
        print_forms: bool=False,
):
    """
    Arguments:
        stem:      The stem to be inflected
        paradigm:  The paradigm to use for inflection
        action:    Whether to print the generated forms or return them as a list
        parse:     Whether to return the generated forms as feature dictionaries (if action is 'return')
    """
    lattice = rewrite.rewrite_lattice(
        fst(stem),
        paradigm.stems_to_forms @ paradigm.feature_label_rewriter,
    )
    word_dicts = decode_feature_label_rewriter(lattice)
    if save_to_tmp:
        df = pd.DataFrame(word_dicts)
        df.to_csv(f'tmp/{stem}_forms.csv', index=False)
    if print_forms:
        for word_dict in word_dicts:
            word_dict = word_dict.copy()
            wordform = word_dict.pop('wordform')
            features_str = ', '.join(f"{k}={v}" for k, v in word_dict.items())
            print(f"{wordform}\t{features_str}")
    return word_dicts

def build_wh_parser(parser_fst) -> pynini.Fst:
    """
    Arguments:
        parser_fst:  An FST mapping from form strings to feature strings
    Returns:
        wh_parser_fst:  An FST mapping from form strings to feature strings
                        with WH suffixes/features added
    Constructs an FST based on `parser_fst` that adds appropriate WH suffixes
    based on the noun class features in the input. Note that this function
    does not handle setting the WH feature flag to 'true'; that should be done
    separately.
    """
    inverse_parser_fst = pynini.invert(parser_fst)
    wh_parsers = []

    for class_prefix in CLASS_PREFIXES:
        class_feature_fsa = SIGMASTAR+fst('class='+class_prefix)+SIGMASTAR
        class_suffix = suffix(f"-{class_prefix}ɛ{HIGH_TONE}")

        class_wh_fst = class_feature_fsa @ inverse_parser_fst @ class_suffix
        class_wh_fst.invert()
        wh_parsers.append(class_wh_fst)

    return pynini.union(*wh_parsers).optimize()