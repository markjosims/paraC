"""
# Noun Paradigm Builder
This module builds the noun paradigm for Tira nouns using data from the noun lexicon.
The 'root' column is used as the lemma, which generally corresponds to the singular nominative form
with a homophone disambiguation suffix if necessary.

Marked features include case (nominative and accusative), number (singular and plural).

TODO: Support inalienably possessed nouns.
"""

import pandas as pd
import pynini
from pynini.lib import features, paradigms, rewrite, pynutil
from src.decorators import output_cache
from src.lexicon.phonology import *
from src.fst_helpers import *
from src.lexicon import load_lexical_data
from src.constants import (
    NOUN_FEATURE_ABBREVIATION_TO_VECTOR,
    BOUNDARY_STR,
    POS_GROUPS,
    POS2CATEGORY,
    POS2ROOT_VECTOR
)
from typing import *

@output_cache(__file__)
def get_nominal_paradigm(part_of_speech: str) -> paradigms.Paradigm:
    """
    Create Paradigm object for the specified nominal part of speech
    (noun or pronoun).
    """
    df = load_lexical_data(part_of_speech=part_of_speech)
    slots = []
    lemma_col = df['root']

    # add forms for all case and number combinations
    for feature_str, feature_vec in NOUN_FEATURE_ABBREVIATION_TO_VECTOR.items():

        # need to filter out empty forms (e.g. no accusative or plural forms for some nouns)
        feature_col = df[feature_str]
        feature_mask = feature_col!=''
        if not feature_mask.any():
            continue
        
        feature_forms = feature_col[feature_mask].tolist()
        lemmata = lemma_col[feature_mask].tolist()
        feature_fsts = []

        # iter through variants of a form (separated by spaces)
        for form, lemma in zip(feature_forms, lemmata):
            for subform in form.split():
                feature_fsts.append(fst(lemma, subform))
        feature_fst = pynini.union(*feature_fsts).optimize()
        slots.append((feature_fst, feature_vec))
    root_fsas = [fst(root) for root in df['root'].tolist()]

    lemma_acceptor = pynini.union(*root_fsas).optimize()
    lemma_feature = POS2ROOT_VECTOR[part_of_speech]
    slots.append((lemma_acceptor, lemma_feature))

    category = POS2CATEGORY[part_of_speech]

    nominal_paradigm = paradigms.Paradigm(
        category=category,
        name=stringify_lexeme_features({"part_of_speech": part_of_speech}),
        slots=slots,
        lemma_feature_vector=lemma_feature,
        stems=root_fsas,
        boundary=fst(BOUNDARY_STR),
    )
    return nominal_paradigm

def get_all_nominal_paradigms() -> List[paradigms.Paradigm]:
    """
    Get paradigms for all nominal parts of speech.
    """
    nominal_paradigms = []
    for pos in POS_GROUPS['nominal']:
        nominal_paradigms.append(get_nominal_paradigm(part_of_speech=pos))
    return nominal_paradigms