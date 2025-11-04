import pandas as pd
import pynini
from pynini.lib import features, paradigms, rewrite, pynutil
from src.cache_decorators import output_cache
from src.phonology import *
from src.fst_helpers import *
from src.lexicon import NOUNS_DF, get_all_noun_data, get_noun_lemmata, get_gloss_for_noun
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
    nouns_df = get_all_noun_data(return_type=pd.DataFrame)
    slots = []
    lemma_col = nouns_df['lemma']
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
    lemma_acceptor = pynini.union(*get_noun_lemmata(wrap_w_fsa=True)).optimize()
    slots.append((lemma_acceptor, NOUN_ROOT))

    noun_paradigm = paradigms.Paradigm(
        category=NOUN,
        name='Nouns',
        slots=slots,
        lemma_feature_vector=NOUN_ROOT,
        stems=get_noun_lemmata(wrap_w_fsa=True),
        boundary=fst(BOUNDARY_STR),
    )
    return noun_paradigm

def parse_noun(noun_form: str, add_gloss: bool=True) -> Dict[str, str]:
    """
    Parse an inflected noun form into its lemma and feature values.

    Arguments:
        noun_form:  str of inflected noun form to parse
    Returns:
        parse:      dict with keys 'form', 'lemma', and feature names
    """
    parses = []
    noun_paradigm = get_noun_paradigm()
    lemmata = noun_paradigm.lemmatize(fst(noun_form))
    for root, feature_vec in lemmata:
        root = decode_byte_str(root)

        parse = feature_vec.values
        if parse['case']=='unmarked':
            # ignore zero feature parses
            continue
        parse['root'] = root
        parse['form'] = noun_form
        if add_gloss:
            parse['gloss']=get_gloss_for_noun(root)
        parses.append(parse)
    return parses