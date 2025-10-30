"""
Form builders for verbs with extension suffixes.
Relies on paradigm building functions from `src.form_builders.verb_forms`.
This module defines verb stems with specific extensions, as well as FSA-based
search functions to determine if a given verb form matches a particular extension pattern.
"""

from src.constants import EXTENSION_MAP, ABBREVIATION2EXTENSION, BOUNDARY_STR
from src.form_builders.verb_forms import get_verb_stem_paradigm, get_verb_paradigm_w_aux, inflect_verb_with_features
from itertools import product
from typing import *
from pynini.lib import paradigms

def get_possible_extension_seqs() -> List[Union[str, Tuple[str, str]]]:
    """
    Returns:
        A list of all possible extension sequences (single and double extensions).
    """
    extension_couples = list(
        product(EXTENSION_MAP.keys(), repeat=2)
    )
    allowed_repeats = ['locative', 'benefactive']
    filtered_extension_couples = [
        couple for couple in extension_couples
        if couple[0] != couple[1] or couple[0] in allowed_repeats
    ]
    single_extensions = list(EXTENSION_MAP.keys())
    all_extension_seqs = single_extensions + filtered_extension_couples
    return all_extension_seqs

def extension_abbreviations_to_long(
    extension_seq: Union[str, Tuple[str, str]]
):
    """
    Arguments:
        extension_seq: A single extension or a tuple of two extensions.
    Returns:
        A list of long-form extension names corresponding to the input.
    """
    if type(extension_seq) == str:
        return ABBREVIATION2EXTENSION[extension_seq]
    else:
        return list(ABBREVIATION2EXTENSION[ext] for ext in extension_seq)

def get_derived_stem_and_fv(
        base_stem: str,
        fv: str,
        extension_seq: Union[str, Sequence[str]]
) -> Tuple[str, str]:
    """
    Arguments:
        base_stem: The root form of the verb.
        fv: FV class for verb.
        extension_seq: A single extension or a sequence of extensions to apply.
    Returns:
        (derived_stem, derived_fv): The derived verb stem and FV class
        with the appropriate extensions applied.

    Given a base verb stem and an extension sequence (e.g., 'causative', 'passive'),
    return the derived stem with the appropriate suffixes.
    """
    derived_stem = base_stem
    if type(extension_seq) == str:
        extension_seq = [extension_seq]
    if extension_seq[0] in ABBREVIATION2EXTENSION:
        extension_seq = extension_abbreviations_to_long(extension_seq)
    outer_fv = fv
    for ext in extension_seq:
        suffix = EXTENSION_MAP[ext]
        if type(suffix) is dict:
            suffix_str, suffix_fv = suffix[outer_fv]
            derived_stem = BOUNDARY_STR.join([derived_stem, suffix_str])
        else: # type(suffix) is tuple
            suffix_str, suffix_fv = suffix
            derived_stem = BOUNDARY_STR.join([derived_stem, suffix_str])
        outer_fv = suffix_fv
    return derived_stem, outer_fv

def build_paradigm_for_extension(
    root: str,
    fv: str,
    extension_seq: Union[str, Sequence[str]]
) -> Tuple[paradigms.Paradigm, paradigms.Paradigm]:
    """
    Arguments:
        root: The root form of the verb.
        fv: FV class for verb.
        extension_seq: A single extension or a sequence of extensions to apply.
    Returns:
        (paradigm_no_aux, paradigm_w_aux):
        A mapping from grammatical feature strings to inflected verb forms.

    Build the full paradigm for a verb with the specified extensions applied.
    """
    derived_stem, derived_fv = get_derived_stem_and_fv(root, fv, extension_seq)
    paradigm_no_aux = get_verb_stem_paradigm(
        stems=derived_stem,
        fv_class=derived_fv,
        paradigm_name=derived_stem
    )
    paradigm_w_aux = get_verb_paradigm_w_aux(paradigm_no_aux)
    return paradigm_no_aux, paradigm_w_aux

def inflect_verb_with_extension(
    root: str,
    fv: str,
    extension_seq: Union[str, Sequence[str]],
    features: Dict[str, str],
    expected_verb_type: Literal['stem', 'stem_and_aux', 'all']='all',
) -> List[str]:
    """
    Arguments:
        root: The root form of the verb.
        fv: FV class for verb.
        extension_seq: A single extension or a sequence of extensions to apply.
        features: A dict mapping feature labels to values.
        expected_verb_type: The expected type of the verb ('stem', 'stem_and_aux', 'all').
    Returns:
        A list of inflected verb forms with the specified extensions applied.

    Inflect a verb with the given extensions and return all possible forms.
    """
    paradigm_no_aux, paradigm_w_aux = build_paradigm_for_extension(
        root, fv, extension_seq
    )
    derived_stem = paradigm_no_aux.stems[0]
    if expected_verb_type == 'stem':
        return inflect_verb_with_features(derived_stem, paradigm_no_aux, features=features)
    elif expected_verb_type == 'stem_and_aux':
        return inflect_verb_with_features(derived_stem, paradigm_w_aux, features=features)
    else:  # expected_verb_type == 'all'        
        forms_no_aux = inflect_verb_with_features(derived_stem, paradigm_no_aux, features=features)
        forms_w_aux = inflect_verb_with_features(derived_stem, paradigm_w_aux, features=features)
        return forms_no_aux + forms_w_aux   
   