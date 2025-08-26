"""
WIP: Script that loads lexical data from .csv files and compiles FSTs mapping
stems to glosses and to principal parts.
"""

import pynini
import pandas as pd
from src.constants import VERB_ROOTS_PATH, ROOT2FV_FST_PATH, ROOT2GLOSS_FST_PATH
from typing import *

VERBS_DF = pd.read_csv(VERB_ROOTS_PATH)


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

def get_roots_for_class(fv_class: str) -> List[str]:
    fv_mask = VERBS_DF['root_fv']==fv_class
    roots = VERBS_DF.loc[fv_mask, 'verb_root'].tolist()
    return roots

def get_all_verb_roots() -> List[str]:
    return VERBS_DF['verb_root'].tolist()

def get_all_verb_roots_and_fvs() -> List[Tuple[str, str]]:
    verb_roots = VERBS_DF['verb_root'].tolist()
    verb_fvs = VERBS_DF['root_fv'].tolist()
    return list(zip(verb_roots, verb_fvs))

def main() -> int:
    root2gloss = get_root2gloss_fst()
    root2gloss.write(ROOT2GLOSS_FST_PATH)

    root2fv = get_root2fv_fst()
    root2fv.write(ROOT2FV_FST_PATH)

    return 0

if __name__ == '__main__':
    main()