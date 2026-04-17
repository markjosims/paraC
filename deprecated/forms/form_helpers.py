"""
# Form helper functions
Helper functions for creating paradigm functions
for various parts of speech.
These include functions for adding suffixes and prefixes
generally, as well as functions for adding class prefixes
and WH suffixes specific to Tira nouns.
"""

from typing import *
from src.constants import CLASS_PREFIXES, HIGH_TONE, INFLECTED_VERB, LOW_TONE, CLASS_PLACEHOLDER
from src.lexicon.phonology import DELETE_SCHWA_BEFORE_VOWEL, INFLECTED_VERB, SIGMASTAR, REMOVE_DOUBLE_BOUNDARIES, Dict, List, Tuple, features, pynini
from src.fst_helpers import fst
import pynini
from pynini import cdrewrite
from pynini.lib import features, paradigms
import pandas as pd

"""
## Generic affix helpers
Functions that wrap paradigms.prefix and paradigms.suffix
using the `fst` factory to string encoding and setting
symbol tables.
"""

def prefix(
        prefix_form: Union[str, Sequence[str], pynini.Fst],
        stem: Union[str, pynini.Fst, None] = None,
        weight: Optional[pynini.WeightLike] = None,
    ) -> pynini.Fst:
    """
    Creates an FST that prefixes `prefix_form` to the given `stem`.
    Note this does not handle any phonological processes nor insertion
    of the boundary symbol; those must be handled separately.

    Arguments:
        prefix_form:    string or list of strings to be accepted by the FST
        stem:           (Optional) string or FST to be used as the stem
        weight:         (Optional) weight value for FST
    Returns:
        f:              FST prefixing the input string(s)
    """
    if stem is None:
        stem = SIGMASTAR
    input_fsa = fst(fst_input=prefix_form, weight=weight)
    return paradigms.prefix(input_fsa, stem)

def suffix(
        suffix_form: Union[str, Sequence[str], pynini.Fst],
        stem: Union[str, pynini.Fst, None] = None,
        weight: Optional[pynini.WeightLike] = None,
    ) -> pynini.Fst:
    """
    Creates an FST that suffixes `suffix_form` to the given `stem`.
    Note this does not handle any phonological processes nor insertion
    of the boundary symbol; those must be handled separately.

    Arguments:
        suffix_form:    string or list of strings to be accepted by the FST
        stem:           (Optional) string or FST to be used as the stem.
                        If None, defaults to SIGMASTAR.
        weight:         (Optional) weight value for FST
    Returns:
        f:              FST suffixing the input string(s)
    """
    if stem is None:
        stem = SIGMASTAR
    input_fsa = fst(fst_input=suffix_form, weight=weight)
    return paradigms.suffix(input_fsa, stem)

"""
## Class marking helpers
Functions for adding class prefixes and WH suffixes to stems.
"""

def add_class_prefix(
        class_agree: str,
        stem: Union[str, pynini.Fst],
        prefix_tone=LOW_TONE
    ) -> pynini.Fst:
    """
    Adds a class prefix to the given stem. Unlike the `prefix` function,
    which simply prepends the prefix, this function also applies
    phonological rules to ensure proper integration of the class prefix
    with the stem (e.g., deleting schwa before a vowel-initial stem).

    Ex:

    # no tone specified, defaults to low tone
    # insert schwa between class prefix and consonant-initial stem
    >>> f = add_class_prefix('l', fst('və̀lɛ̀ð'))
    >>> get_lattice_strs(f)
    ['lə̀-və̀lɛ̀ð']

    # no schwa between class prefix and vowel-initial stem
    >>> f = add_class_prefix('l', fst('àp'))
    >>> get_lattice_strs(f)
    ['l-àp']

    # avoid double boundaries when prefixing
    >>> f = add_class_prefix('l', fst('-ɛ̀'))
    >>> get_lattice_strs(f)
    ['l-ɛ̀']

    Arguments:
        class_agree:    the noun class to which the prefix should agree
        stem:           string or FST describing the stem to which the class prefix
                        should be added
        prefix_tone:    the tone of the prefix (default: low tone)
    Returns:
        An FST describing the stem with the appropriate class prefix added.
    """
    prefix_acceptor = fst(f"{class_agree}ə{prefix_tone}-")
    return (paradigms.prefix(prefix_acceptor, stem)@REMOVE_DOUBLE_BOUNDARIES@DELETE_SCHWA_BEFORE_VOWEL).optimize()


def add_class_prefixes_to_slots(
        slot_list,
        include_ng: bool=False,
        g_as_k: bool=True
    ):
    """
    Given a list of (stem, feature_vector) tuples,
    explode the list by adding class prefixes to each stem
    and updating the feature vector accordingly.

    Arguments:
        slot_list:  A list of (stem, feature_vector) tuples
        include_ng: Whether to include the 'ŋg' class prefix
        g_as_k:     Whether to realize 'g' class as 'k' in onset
    Returns:
        A list of (stem_with_class_prefix, feature_vector_with_class) tuples
        for each class prefix in CLASS_PREFIXES.
    """
    slots_w_class_prefixes = []
    prefixes = CLASS_PREFIXES
    if include_ng:
        prefixes = CLASS_PREFIXES + ['ŋg']
    if g_as_k:
        prefixes = [p if p != 'g' else 'k' for p in prefixes]
    for stem, feature_vector in slot_list:
        category = feature_vector.category
        feature_dict = feature_vector.values.copy()
        feature_dict.pop('class', None)  # remove any existing class feature
        feature_values = [f"{feature}={value}" for feature, value in feature_dict.items()]
        for class_agree in prefixes:
            prefix = class_agree
            # ŋg and k are allomoprhs of g class
            if class_agree in  ['ŋg', 'k']:
                class_agree = 'g'
            features_with_class = features.FeatureVector(category, f"class={class_agree}", *feature_values)
            prefixed_verb = add_class_prefix(class_agree=prefix, stem=stem)
            slots_w_class_prefixes.append((prefixed_verb, features_with_class))
    return slots_w_class_prefixes

def add_class_symbol_replacers_to_slots(slot_list):
    """
    Some adnominal forms contain mark noun class internally,
    which is represented in the lexicon  using a special CLASS_SYMBOL.
    This function replaces the CLASS_SYMBOL with the appropriate class
    prefix, similar to how `add_class_prefixes_to_slots` prepends the
    class prefix.

    Arguments:
        slot_list:  A list of (stem, feature_vector) tuples
    Returns:
        A list of (stem_with_class_prefix, feature_vector_with_class) tuples
        for each slot in `slot_list` with the CLASS_SYMBOL replaced
        by the appropriate class prefix.
    """
    slots_w_class_prefixes = []
    for stem, feature_vector in slot_list:
        category = feature_vector.category
        feature_dict = feature_vector.values.copy()
        feature_dict.pop('class', None)  # remove any existing class feature
        feature_values = [f"{feature}={value}" for feature, value in feature_dict.items()]
        for class_agree in CLASS_PREFIXES:
            prefix = class_agree
            rewrite_rule = cdrewrite(
                tau = fst(CLASS_PLACEHOLDER, prefix),
                l = fst(''),
                r = fst(''),
                sigma_star = SIGMASTAR,
            )
            new_stem = stem @ rewrite_rule
            new_stem.optimize()
            features_with_class = features.FeatureVector(category, f"class={class_agree}", *feature_values)
            slots_w_class_prefixes.append((new_stem, features_with_class))
    return slots_w_class_prefixes

def add_wh_suffix(stem: pynini.Fst, class_agree: str) -> pynini.Fst:
    """
    Add the appropriate WH suffix to a stem based on noun class agreement.
    WH suffixes take the shape -<CL>ɛ́ with a high tone on the vowel, avoiding
    creating a double boundary.

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
    Adds the locative WH suffix -l to the given stem, avoiding double boundaries.

    Arguments:
        stem:           FST describing the stem to which the locative WH suffix should be added
    Returns:
        An FST describing the stem with the locative WH suffix added.
    """
    suffix_acceptor = fst("-l")
    return (paradigms.suffix(suffix_acceptor, stem)@REMOVE_DOUBLE_BOUNDARIES).optimize()


def add_wh_suffixes_to_slots(slot_list):
    """
    Given a list of (stem, feature_vector) tuples,
    explode the list by adding WH suffixes to each stem
    and updating the feature vector accordingly.

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

"""
## Slot aggregation helpers
Functions for aggregating various slot dicts into a single
slot list, performing unions over FSTs with identical feature vectors.
"""

def aggregate_slot_dicts(
        slot_dicts: List[Dict[Tuple[str, str, str], pynini.Fst]],
        category: features.Category,
    ) -> List[Tuple[pynini.Fst, features.FeatureVector]]:
    """
    Aggregate a list of slot dicts into a single slot dict.
    """
    aggregated_slot_dict = {}
    for slot_dict in slot_dicts:
        for feature_tuple, fst in slot_dict.items():
            if feature_tuple in aggregated_slot_dict:
                existing_fst = aggregated_slot_dict[feature_tuple]
                combined_fst = existing_fst | fst
                combined_fst.optimize()
                aggregated_slot_dict[feature_tuple] = combined_fst
            else:
                aggregated_slot_dict[feature_tuple] = fst
    slot_list = [
        (fst, features.FeatureVector(category, *feature_tuple))
        for feature_tuple, fst in aggregated_slot_dict.items()
    ]
    return slot_list


"""
## Marker and feature builders
Person marking for verbs and auxiliaries creates a large combinatorial
space of possible forms and feature values. To aid in building these forms,
`aux_forms.py` and `verb_forms.py` define various dataclasses
that organize person markers for auxiliary verbs and inflected verbs
respectively, allowing paradigms of person markers to be built programmatically.

The functions in this section encapsulate logic for interfacing with these
dataclasses and for currying TAMD feature values into feature vector builders.
"""

def _get_affix_rule(
        affix: Union[str, List[str], Dict[str, Any]],
        affix_funct: Callable[[Union[str, List[str]]],pynini.Fst]
    ) -> pynini.Fst:
    """
    Helper function for `make_marker_rule`.
    Given an affix specification (string, list of strings, or marker dict),
    return the corresponding FST rule.

    Arguments:
        affix:          The affix specification
        affix_funct:    The function to use to create the FST (e.g., `prefix` or `suffix`)
    Returns:
        The corresponding FST rule
    """
    if type(affix) is str:
        return affix_funct(affix)
    elif type(affix) is list:
        return affix_funct(affix)
    elif type(affix) is dict:
        required = affix.get('required', None)
        optional = affix.get('optional', None)
        if required is None or optional is None:
            raise ValueError(f"Marker dict must contain both 'required' and 'optional' keys: {affix}")
        required_rule = affix_funct(required)
        optional_rule = affix_funct(optional).ques
        return required_rule + optional_rule
    else:
        raise ValueError(f"Unknown affix format: {affix}")


def make_marker_rule(marker: Dict[str, Any]) -> pynini.Fst:
    """
    Create FST from a marker dictionary, where the keys indicate
    the logic for combining prefix and suffix parts.

    Handles formats:
    - {'prefix': 'X'} -> prefix('X')
    - {'suffix': 'X'} -> suffix('X')
    - {'suffix': ['X', 'Y']} -> suffix('X')|suffix('Y')
    - {'prefix': 'X', 'suffix': 'Y'}
        -> prefix('X') @ suffix('Y')
    - {'suffix': {'required': 'X', 'optional': 'Y'}}
        -> suffix('X') + suffix('Y').ques

    """
    suffix_str = marker.get('suffix', None)
    prefix_str = marker.get('prefix', None)


    if prefix_str is not None and suffix_str is not None:
        prefix_rule = _get_affix_rule(prefix_str, prefix)
        suffix_rule = _get_affix_rule(suffix_str, suffix)
        return prefix_rule @ suffix_rule
    elif prefix_str is not None:
        prefix_rule = _get_affix_rule(prefix_str, prefix)
        return prefix_rule
    elif suffix_str is not None:
        suffix_rule = _get_affix_rule(suffix_str, suffix)
        return suffix_rule

    raise ValueError(f"Unknown marker format: {marker}")

def make_feature_builder(category, tamd_strs: List[str]):
    """
    Returns a function that creates feature vectors for a given category and TAMD.
    Curries the provided TAMD values into the returned function, and allows the class,
    subject, object, and wh features to be specified when called. Any unspecified features
    default to 'unmarked'.

    Ex:
    >>> ipfv_features = make_feature_builder(INFLECTED_AUX, ["tam=imperfective", "deixis=unmarked"])
    >>> feature_vec = ipfv_features(sbj='1sg', obj='2sg', cl='unmarked', wh='unmarked')
    >>> print(feature_vec)
    # not actual output, but illustrative
    Category: INFLECTED_AUX
    Values: tam=imperfective, deixis=unmarked, subject=1sg, object=2sg, class=unmarked, wh=unmarked

    Arguments:
        category:   The feature category (e.g., INFLECTED_AUX, INFLECTED_VERB)
        tamd_strs:  List of TAMD feature strings (e.g., ["tam=imperfective", "deixis=unmarked"])

    Returns:
        A function get_features(sbj, obj, cl, wh) that returns a FeatureVector
    """
    def get_features(sbj: str = 'unmarked', obj: str = 'unmarked',
                     cl: str = 'unmarked', wh: str = 'unmarked') -> features.FeatureVector:
        features_list = [category]
        features_list.extend(tamd_strs)
        features_list.append(f"subject={sbj}")
        features_list.append(f"object={obj}")
        features_list.append(f"class={cl}")
        features_list.append(f"wh={wh}")
        return features.FeatureVector(*features_list)
    return get_features


def add_1pl_incl_r_suffix(
    slots: List[Tuple[pynini.Fst, features.FeatureVector]]
) -> List[Tuple[pynini.Fst, features.FeatureVector]]:
    """Add -ŕ suffix for 1pl.incl forms in the given slots."""
    for rule, features_vec in slots[:]:
        new_rule = rule @ suffix('-ŕ')
        for role in ['subject', 'object']:
            new_features = features_vec.values.copy()
            new_features[role] = '1pl.incl'
            new_features_vec = features.FeatureVector(
                INFLECTED_VERB,
                *[f"{k}={v}" for k, v in new_features.items()]
            )
            slots.append((new_rule, new_features_vec))
    return slots


def add_imperative_object_markers(
    slots: List[tuple[pynini.Fst, features.FeatureVector]]
) -> List[Tuple[pynini.Fst, features.FeatureVector]]:
    """
    TODO: Add object markers for imperative forms.
    Object: 3pl: -l
    """
    ...


def add_dependent_markers(
    slots: List[Tuple[pynini.Fst, features.FeatureVector]]
) -> List[Tuple[pynini.Fst, features.FeatureVector]]:
    """TODO: Add dependent markers."""
    ...