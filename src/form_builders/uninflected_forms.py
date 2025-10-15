from src.glossing import REMOVE_HOMOPHONE_TAG
from src.fst_helpers import fst, decode_fst_string
from src.lexicon import get_pos_and_gloss_for_uninflected_word, get_uninflected_word_data
import pynini
from typing import *
import pandas as pd

def build_uninflected_word_fst() -> pynini.Fst:
    """
    Build an FST accepting uninflected words and mapping homophones
    to strings with homophone tags.
    """
    uninflected_word_df = get_uninflected_word_data(return_type=pd.DataFrame)
    words = uninflected_word_df['word'].tolist()
    word_fsas = [fst(word) for word in words]
    word_fsas_notag = [word@REMOVE_HOMOPHONE_TAG for word in word_fsas]
    word_fsts = [
        fst(word_fsa_notag, word_fsa)
        for word_fsa, word_fsa_notag in zip(word_fsas, word_fsas_notag)
    ]
    word_fst = pynini.union(*word_fsts).optimize()
    return word_fst

UNINFLECTED_WORD_FST = build_uninflected_word_fst()

def parse_uninflected_word(form: str) -> Dict[str, str]:
    """
    Wraps `get_pos_and_gloss_for_uninflected_word` to provide a consistent
    interface with other parse functions.

    Arguments:
        form:  The uninflected word to parse.
    
    Returns:
        parse:  A dictionary with keys 'word', 'part_of_speech', and 'gloss'.
    """
    pos, gloss = get_pos_and_gloss_for_uninflected_word(form)
    return {
        'word': form,
        'part_of_speech': pos,
        'gloss': gloss
    }