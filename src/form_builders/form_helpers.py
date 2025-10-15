"""
Helper functions for creating paradigm functions
for various parts of speech.
"""

from typing import *
from src.fst_helpers import decode_byte_str, fst
from src.constants import CLASS_PREFIXES, LOW_TONE
from src.glossing import feature_str_to_dict
from src.phonology import DELETE_SCHWA_BEFORE_VOWEL
import pynini
from pynini.lib import features, paradigms, rewrite


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
    return (paradigms.prefix(prefix_acceptor, stem)@DELETE_SCHWA_BEFORE_VOWEL).optimize()


def add_class_prefixes_to_slots(slot_list):
    """
    Arguments:
        slot_list:  A list of (stem, feature_vector) tuples
    Returns:
        A list of (stem_with_class_prefix, feature_vector_with_class) tuples
        for each class prefix in CLASS_PREFIXES.
    """
    slots_w_class_prefixes = []
    for stem, feature_vector in slot_list:
        category = feature_vector.category
        feature_dict = feature_vector.values.copy()
        feature_dict.pop('class', None)  # remove any existing class feature
        feature_values = [f"{feature}={value}" for feature, value in feature_dict.items()]
        for class_agree in CLASS_PREFIXES:
            features_with_class = features.FeatureVector(category, f"class={class_agree}", *feature_values)
            prefixed_verb = add_class_prefix(stem, class_agree)
            slots_w_class_prefixes.append((prefixed_verb, features_with_class))
    return slots_w_class_prefixes


def generate_forms(
        stem: str,
        paradigm: paradigms.Paradigm,
        action: Literal['print', 'return']='print',
        parse: bool=False
):
    """
    Arguments:
        stem:       The stem to be inflected
        paradigm:  The paradigm to use for inflection
        action:    Whether to print the generated forms or return them as a list
        parse:     Whether to return the generated forms as feature dictionaries (if action is 'return')
    """
    lattice = rewrite.rewrite_lattice(
        fst(stem),
        paradigm.stems_to_forms @ paradigm.feature_label_rewriter,
    )
    wordforms = []
    for wordform in rewrite.lattice_to_strings(lattice):
        if action=='return' and parse:
            parsed_wordform = feature_str_to_dict(wordform)
            wordforms.append(parsed_wordform)
        elif action=='return':
            wordforms.append(wordform)
        else:
            byte_word = wordform.split('[')[0]
            word = decode_byte_str(byte_word)
            wordform = wordform.replace(byte_word, word)
            print(wordform)
    if action=='return':
        return wordforms

