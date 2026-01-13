"""
# Adnominal form builders
This module builds the paradigms for Tira adjectives and pronouns
using data from the adjective and pronoun lexicons. The 'root'
column is used as the lemma for all adnominal forms. For adjectives,
this corresponds to the adjectival root with no tone marked (since
adjectives take default low tone). For pronouns, this corresponds to
the root form with no class prefix, but with tone marked, since adnominal
pronouns have lexical tone.

See src/constants/features.py for more information on adnominal
part of speech.
"""


from pynini.lib import paradigms, features
from typing import *
from src.cache_decorators import output_cache
from src.lexicon import load_lexical_data
from src.form_builders.form_helpers import add_class_prefixes_to_slots, add_class_symbol_replacers_to_slot
from src.constants import (
    ADJECTIVE, ADJECTIVE_ROOT, POS_GROUPS,
    POS2ROOT_VECTOR, POS2CATEGORY, BOUNDARY_STR
)
from src.lexicon.phonology import ALL_LOW_TONE_RULE, SIGMASTAR
from src.fst_helpers import fst, stringify_lexeme_features
import pandas as pd

@output_cache(__file__)
def get_adjective_paradigm() -> paradigms.Paradigm:
    adj_data = load_lexical_data(part_of_speech='adjective')
    adj_roots = [fst(root) for root in adj_data['root'].tolist()]

    inflected_slot = (ALL_LOW_TONE_RULE, ADJECTIVE_ROOT)
    root_slot = (SIGMASTAR, ADJECTIVE_ROOT)

    slots = [root_slot]
    slots += add_class_prefixes_to_slots([inflected_slot])
    adj_paradigm = paradigms.Paradigm(
        category=ADJECTIVE,
        slots=slots,
        stems=adj_roots,
        boundary=fst(BOUNDARY_STR),
        lemma_feature_vector=ADJECTIVE_ROOT,
        name=stringify_lexeme_features({"part_of_speech": 'adjective'}),
    )
    return adj_paradigm

@output_cache(__file__)
def get_adnominal_paradigm(part_of_speech: str) -> paradigms.Paradigm:
    adnominal_data = load_lexical_data(part_of_speech=part_of_speech)
    adnominal_roots = [fst(root) for root in adnominal_data['root'].tolist()]
    
    root_vector = POS2ROOT_VECTOR[part_of_speech]
    category = POS2CATEGORY[part_of_speech]

    inflected_slot = (ALL_LOW_TONE_RULE, root_vector)
    root_slot = (SIGMASTAR, root_vector)

    slots = [root_slot]
    slots += add_class_symbol_replacers_to_slot(inflected_slot)
    adnominal_paradigm = paradigms.Paradigm(
        category=category,
        slots=slots,
        stems=adnominal_roots,
        boundary=fst(BOUNDARY_STR),
        lemma_feature_vector=root_vector,
        name=stringify_lexeme_features({"part_of_speech": part_of_speech}),
    )
    return adnominal_paradigm

def get_all_adnominal_paradigms() -> List[paradigms.Paradigm]:
    """
    Get paradigms for all adnominal parts of speech.
    """
    adnominal_paradigms = []
    for pos in POS_GROUPS['adnominal']:
        adnominal_paradigms.append(get_adnominal_paradigm(part_of_speech=pos))
    return adnominal_paradigms