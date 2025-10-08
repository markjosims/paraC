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
    FUZZY_NOUNS_PATH,
)
from src.fst_helpers import fst
from typing import *
import json

VERBS_DF = pd.read_csv(VERB_ROOTS_PATH, keep_default_na=False)
GOLD_VERBS_DF = pd.read_csv(GOLD_VERBS_PATH, keep_default_na=False)
NOUNS_DF = pd.read_csv(NOUNS_PATH, keep_default_na=False)
FUZZY_NOUNS_DF = pd.read_csv(FUZZY_NOUNS_PATH, keep_default_na=False)

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

def get_all_verb_data() -> List[Tuple[str, str, str]]:
    verb_roots = VERBS_DF['verb_root'].tolist()
    verb_fvs = VERBS_DF['root_fv'].tolist()
    verb_senses = VERBS_DF['root_sense']
    return list(zip(verb_roots, verb_fvs, verb_senses)) 

def get_gold_verbs() -> List[Dict[str, str]]:
    return GOLD_VERBS_DF.to_dict(orient='records')

def get_gold_paradigms() -> List[Dict[str, Any]]:
    with open(GOLD_PARADIGMS_PATH) as f:
        gold_paradigms = json.load(f)
    return gold_paradigms

def get_fuzzy_nouns() -> List[Dict[str, str]]:
    return FUZZY_NOUNS_DF.to_dict(orient='records')

def get_noun_lemmata(wrap_w_fsa: bool=False) -> List[str]:
    lemmata = NOUNS_DF['lemma'].tolist()
    if wrap_w_fsa:
        lemmata = [fst(lemma) for lemma in lemmata]
    return lemmata

def get_gloss_for_noun(lemma: str) -> str:
    lemma_mask = NOUNS_DF['lemma']==lemma
    gloss = NOUNS_DF.loc[lemma_mask, 'gloss'].item()
    return gloss

def main() -> int:
    root2gloss = get_root2gloss_fst()
    root2gloss.write(ROOT2GLOSS_FST_PATH)

    root2fv = get_root2fv_fst()
    root2fv.write(ROOT2FV_FST_PATH)

    return 0

if __name__ == '__main__':
    main()