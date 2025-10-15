"""
WIP: Script that loads lexical data from .csv files and compiles FSTs mapping
stems to glosses and to principal parts.
"""

import pynini
import pandas as pd
from src.constants import (
    VERB_ROOTS_PATH,
    ROOT2FV_FST_PATH,
    ROOT2GLOSS_FST_PATH,
    GOLD_VERBS_PATH,
    GOLD_PARADIGMS_PATH,
    NOUNS_PATH,
    GOLD_NOUNS_PATH,
    ADJECTIVES_PATH,
    GOLD_ADJECTIVES_PATH,
    UNINFLECTED_WORDS_PATH,
)
from src.fst_helpers import fst
from typing import *
import json

VERBS_DF = pd.read_csv(VERB_ROOTS_PATH, keep_default_na=False)
GOLD_VERBS_DF = pd.read_csv(GOLD_VERBS_PATH, keep_default_na=False)
NOUNS_DF = pd.read_csv(NOUNS_PATH, keep_default_na=False)
GOLD_NOUNS_DF = pd.read_csv(GOLD_NOUNS_PATH, keep_default_na=False)
ADJECTIVES_DF = pd.read_csv(ADJECTIVES_PATH, keep_default_na=False)
GOLD_ADJECTIVES_DF = pd.read_csv(GOLD_ADJECTIVES_PATH, keep_default_na=False)
UNINFLECTED_WORDS_DF = pd.read_csv(UNINFLECTED_WORDS_PATH, keep_default_na=False)

class LexemeNotFoundError(Exception):
    """
    Raised when a root is not found in a given paradigm.
    """
    pass

def get_root2gloss_fst() -> pynini.Fst:
    root2gloss_strs = [list(t) for t in zip(
        VERBS_DF['verb_root'].tolist(),
        VERBS_DF['root_sense'].tolist())
    ]
    root2gloss = pynini.string_map(root2gloss_strs)
    return root2gloss

def get_root2fv_fst() -> pynini.Fst:
    root2fv_strs = [list(t) for t in zip(
        VERBS_DF['verb_root'].tolist(),
        VERBS_DF['root_fv'].tolist())
    ]
    root2fv = pynini.string_map(root2fv_strs)
    return root2fv

def get_gloss_for_verb(verb_root: str) -> str:
    root_mask = VERBS_DF['verb_root']==verb_root
    if root_mask.sum()==0:
        raise LexemeNotFoundError(f"Root {verb_root} not found in verb lexicon.")
    if root_mask.sum()>1:
        raise LexemeNotFoundError(f"Root {verb_root} found multiple times in verb lexicon.")
    gloss = VERBS_DF.loc[root_mask, 'root_sense'].item()
    return gloss


def get_roots_for_class(fv_class: str, wrap_w_fsa: bool=False) -> List[str]:
    fv_mask = VERBS_DF['root_fv']==fv_class
    roots = VERBS_DF.loc[fv_mask, 'verb_root'].tolist()
    if wrap_w_fsa:
        roots = [fst(root) for root in roots]
    return roots

def get_all_verb_roots() -> List[str]:
    return VERBS_DF['verb_root'].tolist()

def get_all_verb_roots_and_fvs() -> List[Tuple[str, str]]:
    verb_roots = VERBS_DF['verb_root'].tolist()
    verb_fvs = VERBS_DF['root_fv'].tolist()
    return list(zip(verb_roots, verb_fvs))

def get_verb_gloss_and_fvs() -> List[Tuple[str, str, str]]:
    verb_roots = VERBS_DF['verb_root'].tolist()
    verb_fvs = VERBS_DF['root_fv'].tolist()
    verb_glosses = VERBS_DF['root_sense'].tolist()
    return list(zip(verb_roots, verb_fvs, verb_glosses))

def get_all_verb_data(
        return_type: Union[list, pd.DataFrame]=list
) -> Union[pd.DataFrame, List[Tuple[Any]]]:
    if return_type == pd.DataFrame:
        return VERBS_DF
    return VERBS_DF.to_dict(orient='records')

def get_gold_verbs() -> List[Dict[str, str]]:
    return GOLD_VERBS_DF.to_dict(orient='records')

def get_gold_paradigms() -> List[Dict[str, Any]]:
    with open(GOLD_PARADIGMS_PATH) as f:
        gold_paradigms = json.load(f)
    return gold_paradigms

def get_gold_nouns() -> List[Dict[str, str]]:
    return GOLD_NOUNS_DF.to_dict(orient='records')

def get_noun_lemmata(wrap_w_fsa: bool=False) -> List[str]:
    lemmata = NOUNS_DF['lemma'].tolist()
    if wrap_w_fsa:
        lemmata = [fst(lemma) for lemma in lemmata]
    return lemmata

def get_all_noun_data(
        return_type: Union[list, pd.DataFrame]=list
) -> Union[pd.DataFrame, List[Tuple[str, str]]]:
    if return_type == pd.DataFrame:
        return NOUNS_DF
    return NOUNS_DF.to_dict(orient='records')

def get_gloss_for_noun(lemma: str) -> str:
    lemma_mask = NOUNS_DF['lemma']==lemma
    if lemma_mask.sum()==0:
        raise LexemeNotFoundError(f"Lemma {lemma} not found in noun lexicon.")
    if lemma_mask.sum()>1:
        raise LexemeNotFoundError(f"Lemma {lemma} found multiple times in noun lexicon.")
    gloss = NOUNS_DF.loc[lemma_mask, 'gloss'].item()
    return gloss

def get_adjective_roots(wrap_w_fsa: bool=False) -> List[str]:
    roots = ADJECTIVES_DF['root'].tolist()
    if wrap_w_fsa:
        roots = [fst(root) for root in roots]
    return roots

def get_gloss_for_adjective(root: str) -> str:
    root_mask = ADJECTIVES_DF['root']==root
    if root_mask.sum()==0:
        raise LexemeNotFoundError(f"Root {root} not found in adjective lexicon.")
    if root_mask.sum()>1:
        raise LexemeNotFoundError(f"Root {root} found multiple times in adjective lexicon.")
    gloss = ADJECTIVES_DF.loc[root_mask, 'gloss'].item()
    return gloss

def get_gold_adjectives() -> List[Dict[str, str]]:
    return GOLD_ADJECTIVES_DF.to_dict(orient='records')

def get_all_adjective_data(
        return_type: Union[list, pd.DataFrame]=list
) -> Union[pd.DataFrame, List[Tuple[str, str]]]:
    if return_type == pd.DataFrame:
        return ADJECTIVES_DF
    return ADJECTIVES_DF.to_dict(orient='records')

def get_uninflected_word_data(
        return_type: Union[list, pd.DataFrame]=list
) -> Union[pd.DataFrame, List[Tuple[Any]]]:
    if return_type == pd.DataFrame:
        return UNINFLECTED_WORDS_DF
    return UNINFLECTED_WORDS_DF.to_dict(orient='records')

def get_pos_and_gloss_for_uninflected_word(word: str) -> Tuple[str, str]:
    word_mask = UNINFLECTED_WORDS_DF['word']==word
    if word_mask.sum()==0:
        raise LexemeNotFoundError(f"Word {word} not found in uninflected word lexicon.")
    if word_mask.sum()>1:
        raise LexemeNotFoundError(f"Word {word} found multiple times in uninflected word lexicon.")
    pos = UNINFLECTED_WORDS_DF.loc[word_mask, 'part_of_speech'].item()
    gloss = UNINFLECTED_WORDS_DF.loc[word_mask, 'gloss'].item()
    return pos, gloss

def main() -> int:
    root2gloss = get_root2gloss_fst()
    root2gloss.write(ROOT2GLOSS_FST_PATH)

    root2fv = get_root2fv_fst()
    root2fv.write(ROOT2FV_FST_PATH)

    return 0

if __name__ == '__main__':
    main()