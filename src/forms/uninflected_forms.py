"""
# FST for uninflected words
FST building function for uninflected words. Uninflected words
include adverbs, conjunctions, prepositions, adpositions, particles
and interjections [TODO]. These words do not take inflectional morphology,
and so are represented with a single form in the lexicon. The FST is an
acceptor for most forms, with the exception of homophones, which are
mapped from plain input strings to forms with homophone disambiguation tags
in output, e.g. "nɛ̀" -> "nɛ̀(1)" 'in', "nɛ̀(2)" 'and'.
"""

from src.decorators import fst_cache
from src.lexicon.phonology import REMOVE_HOMOPHONE_TAG
from src.fst_helpers import decode_byte_str, fst, vectorize_lexeme_string
from src.lexicon import load_lexical_data
import pynini
from pynini.lib import rewrite
from typing import *
import pandas as pd

@fst_cache(__file__)
def get_uninflected_word_fst() -> pynini.Fst:
    """
    Build an FST accepting uninflected words and mapping homophones
    to strings with homophone tags.
    """
    uninflected_word_df = load_lexical_data(part_of_speech='uninflected')
    words = uninflected_word_df['root'].tolist()
    part_of_speech = uninflected_word_df['part_of_speech'].tolist()
    pos_strs = [f"part_of_speech={p}" for p in part_of_speech]
    lexeme_flag_acceptors = [
        vectorize_lexeme_string(tag).acceptor for tag in pos_strs
    ]
    word_fsas = [fst(word) for word in words]
    word_fsas_notag = [(word@REMOVE_HOMOPHONE_TAG).project('output') for word in word_fsas]
    word_fsts = [
        fst(word_fsa_notag, word_fsa+lexeme_flag_acceptor)
        for word_fsa, word_fsa_notag, lexeme_flag_acceptor
        in zip(word_fsas, word_fsas_notag, lexeme_flag_acceptors)
    ]
    word_fst = pynini.union(*word_fsts).optimize()
    return word_fst