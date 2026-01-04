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
from src.cache_decorators import output_cache
from src.lexicon.phonology import *
from src.fst_helpers import *
from src.lexicon import get_all_noun_data, get_noun_roots
from src.constants import (
    NOUN_FEATURE_ABBREVIATION_TO_VECTOR,
    NOUN_ROOT,
    NOUN,
    BOUNDARY_STR,
)
from typing import *

@output_cache(__file__)
def get_noun_paradigm() -> paradigms.Paradigm:
    """
    Create Paradigm object for Tira nouns.
    """
    nouns_df = get_all_noun_data(return_type='dataframe')
    slots = []
    lemma_col = nouns_df['root']
    for feature_str, feature_vec in NOUN_FEATURE_ABBREVIATION_TO_VECTOR.items():
        feature_col = nouns_df[feature_str]
        feature_mask = feature_col!=''
        
        feature_forms = feature_col[feature_mask].tolist()
        lemmata = lemma_col[feature_mask].tolist()
        feature_fsts = []

        for form, lemma in zip(feature_forms, lemmata):
            for subform in form.split():
                feature_fsts.append(fst(lemma, subform))
        feature_fst = pynini.union(*feature_fsts).optimize()
        slots.append((feature_fst, feature_vec))
    lemma_acceptor = pynini.union(*get_noun_roots(wrap_w_fsa=True)).optimize()
    slots.append((lemma_acceptor, NOUN_ROOT))

    noun_paradigm = paradigms.Paradigm(
        category=NOUN,
        name=stringify_lexeme_features({"part_of_speech": 'noun'}),
        slots=slots,
        lemma_feature_vector=NOUN_ROOT,
        stems=get_noun_roots(wrap_w_fsa=True),
        boundary=fst(BOUNDARY_STR),
    )
    return noun_paradigm