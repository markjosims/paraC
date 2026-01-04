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
from src.lexicon import get_adjective_roots
from src.form_builders.form_helpers import add_class_prefix, add_class_prefixes_to_slots
from src.constants import ADJECTIVE, ADJECTIVE_ROOT, ADNOMINAL_CLASS_VALUES, BOUNDARY_STR
from src.lexicon.phonology import ALL_LOW_TONE_RULE, SIGMASTAR
from src.fst_helpers import fst, stringify_lexeme_features
import pandas as pd

@output_cache(__file__)
def get_adjective_paradigm() -> paradigms.Paradigm:
    adj_lemmata = get_adjective_roots(wrap_w_fsa=True)

    inflected_slot = (ALL_LOW_TONE_RULE, ADJECTIVE_ROOT)
    root_slot = (SIGMASTAR, ADJECTIVE_ROOT)

    slots = [root_slot]
    slots += add_class_prefixes_to_slots([inflected_slot])
    adj_paradigm = paradigms.Paradigm(
        category=ADJECTIVE,
        slots=slots,
        stems=adj_lemmata,
        boundary=fst(BOUNDARY_STR),
        lemma_feature_vector=ADJECTIVE_ROOT,
        name=stringify_lexeme_features({"part_of_speech": 'adjective'}),
    )
    return adj_paradigm

@output_cache(__file__)
def get_demonstrative_paradigm() -> paradigms.Paradigm:
    ...