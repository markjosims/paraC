"""
# Form helper functions
Helper functions for creating paradigm functions
for various parts of speech.
These include functions for adding suffixes and prefixes
generally, as well as functions for adding class prefixes
and WH suffixes specific to Tira nouns.
"""

from typing import *
from src.fst_helpers import fst
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
        fst_input:  string or list of strings to be accepted by the FST
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
        fst_input:  string or list of strings to be accepted by the FST
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

def add_wh_suffix(stem: pynini.Fst, class_agree: str) -> pynini.Fst:
    """
    Arguments:
        stem:           FST describing the stem to which the class prefix should be added
        class_agree:    the noun class to which the prefix should agree
    Returns:
        An FST describing the stem with the appropriate WH suffix added.
    """
    suffix_acceptor = fst(f"-{class_agree}ɛ{HIGH_TONE}")
    return (paradigms.suffix(suffix_acceptor, stem)@REMOVE_DOUBLE_BOUNDARIES).optimize()

def add_wh_loc_suffix(stem: pynini.Fst) -> pynini.Fst:
    """
    Arguments:
        stem:           FST describing the stem to which the locative WH suffix should be added
    Returns:
        An FST describing the stem with the locative WH suffix added.
    """
    suffix_acceptor = fst("-l")
    return (paradigms.suffix(suffix_acceptor, stem)@REMOVE_DOUBLE_BOUNDARIES).optimize()


def add_wh_suffixes_to_slots(slot_list):
    """
    Arguments:
        slot_list:  A list of (stem, feature_vector) tuples
    Returns:
        A list of (stem_with_wh_suffix, feature_vector_with_class) tuples
        for each slot in `slot_list` with a defined class agreement
        appended to the original `slot_list`.
    """
    slots_w_wh_suffixes = []
    for stem, feature_vector in slot_list:
        category = feature_vector.category
        class_feature_dict = feature_vector.values.copy()
        class_agree = class_feature_dict['class']
        if class_agree == 'unmarked':
            continue

        class_feature_dict['wh']='class'
        feature_values = [f"{feature}={value}" for feature, value in class_feature_dict.items()]
        class_wh_suffix = add_wh_suffix(stem, class_agree)
        class_feature_vec = features.FeatureVector(category, *feature_values)
        slots_w_wh_suffixes.append((class_wh_suffix, class_feature_vec))

        loc_feature_dict = class_feature_dict.copy()
        loc_feature_dict['wh']='locative'
        feature_values = [f"{feature}={value}" for feature, value in loc_feature_dict.items()]
        loc_feature_vec = features.FeatureVector(category, *feature_values)
        loc_wh_suffix = add_wh_loc_suffix(stem)
        slots_w_wh_suffixes.append((loc_wh_suffix, loc_feature_vec))
    return slot_list+slots_w_wh_suffixes

