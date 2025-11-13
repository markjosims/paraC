from src.cache_decorators import fst_cache
from src.lexicon.phonology import REMOVE_HOMOPHONE_TAG
from src.fst_helpers import decode_byte_str, fst, vectorize_lexeme_string
from src.lexicon import get_pos_and_gloss_for_uninflected_word, get_uninflected_word_data
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
    uninflected_word_df = get_uninflected_word_data(return_type=pd.DataFrame)
    words = uninflected_word_df['word'].tolist()
    pos = uninflected_word_df['part_of_speech'].tolist()
    pos_strs = [f"part_of_speech={p}" for p in pos]
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

def parse_uninflected_word(form: str) -> List[Dict[str, str]]:
    """
    Wraps `get_pos_and_gloss_for_uninflected_word` to provide a consistent
    interface with other parse functions. The 'form' key is equivalent to the
    'root' key without homophone tags, if applicable.

    Arguments:
        form:  The uninflected word to parse.
    
    Returns:
        parse:  A dictionary with keys 'root', 'form', 'part_of_speech', and 'gloss'.
    """
    parses = []
    uninflected_word_fst = get_uninflected_word_fst()
    lattice = (fst(form) @ uninflected_word_fst).project('output')
    roots = rewrite.lattice_to_strings(lattice)
    for root in roots:
        root = decode_byte_str(root)
        pos, gloss = get_pos_and_gloss_for_uninflected_word(root)
        root_parse = {
            'form': form,
            'root': root,
            'part_of_speech': pos,
            'gloss': gloss
        }
        parses.append(root_parse)

    return parses