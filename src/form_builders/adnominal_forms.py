from pynini.lib import paradigms, features
from typing import *
from src.cache_decorators import output_cache
from src.lexicon import get_adjective_roots, get_gloss_for_adjective, get_all_adjective_data
from src.form_builders.form_helpers import add_class_prefix, add_class_prefixes_to_slots
from src.constants import ADJECTIVE, ADJECTIVE_ROOT, ADJECTIVE_CLASS_VALUES, BOUNDARY_STR
from src.lexicon.phonology import ALL_LOW_TONE_RULE, SIGMASTAR
from src.fst_helpers import decode_byte_str, decode_fst_string, fst, stringify_lexeme_features
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
def get_pronoun_paradigm() -> paradigms.Paradigm:
    ...

def parse_adjective(form: str, add_gloss: bool=True) -> Dict[str, str]:
    raise DeprecationWarning("parse_adjective is deprecated. Use parse_word instead.")

def inflect_adjective_with_features(root: str, agree_class: str) -> str:
    raise DeprecationWarning("inflect_adjective_with_features is deprecated. Use inflect_word instead.")