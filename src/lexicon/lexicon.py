"""
WIP: Script that loads lexical data from .csv files and compiles FSTs mapping
stems to glosses and to principal parts.
"""

import os
import pandas as pd
from src.cache_decorators import output_cache
from src.constants import (
    ALL_POSSIBLE_EXTENSION_SEQS,
    FV_CLASSES,
    GOLD_PERSON_MARKING_PATH,
    GOLD_UNINFLECTED_WORDS_PATH,
    VERB_ROOTS_PATH,
    GOLD_VERBS_PATH,
    GOLD_AUXS_PATH,
    GOLD_VERBS_DERIVED_PATH,
    GOLD_PARADIGMS_PATH,
    NOUNS_PATH,
    GOLD_NOUNS_PATH,
    ADJECTIVES_PATH,
    GOLD_ADJECTIVES_PATH,
    UNINFLECTED_WORDS_PATH,
    AUX_LEMMA_STR
)
from src.lexicon.extension_suffixes import get_derived_stem_and_fv
from src.fst_helpers import fst
from typing import *
import json

class LexemeNotFoundError(Exception):
    """
    Raised when a root is not found in a given paradigm.
    """
    pass

def get_roots_for_class(fv_class: str, wrap_w_fsa: bool=False, include_extensions: bool=False) -> List[str]:
    if include_extensions:
        verbs_df = get_all_verb_data(return_type=pd.DataFrame)
    else:
        verbs_df = get_verb_root_data(return_type=pd.DataFrame)
    fv_mask = verbs_df['fv']==fv_class
    roots = verbs_df.loc[fv_mask, 'verb_root'].str.replace('-', '').tolist()
    if wrap_w_fsa:
        roots = [fst(root) for root in roots]
    return roots

def get_all_verb_roots() -> List[str]:
    verbs_df = pd.read_csv(VERB_ROOTS_PATH, keep_default_na=False)
    return verbs_df['verb_root'].tolist()

def get_all_verb_roots_and_fvs() -> List[Tuple[str, str]]:
    verbs_df = pd.read_csv(VERB_ROOTS_PATH, keep_default_na=False)
    verb_roots = verbs_df['verb_root'].tolist()
    verb_fvs = verbs_df['fv'].tolist()
    return list(zip(verb_roots, verb_fvs))

def get_verb_gloss_and_fvs() -> List[Tuple[str, str, str]]:
    verbs_df = pd.read_csv(VERB_ROOTS_PATH, keep_default_na=False)
    verb_roots = verbs_df['verb_root'].tolist()
    verb_fvs = verbs_df['fv'].tolist()
    verb_glosses = verbs_df['gloss'].tolist()
    return list(zip(verb_roots, verb_fvs, verb_glosses))

def get_verb_root_data(
        return_type: Union[list, pd.DataFrame]=list
) -> Union[pd.DataFrame, List[Tuple[Any]]]:
    verbs_df = pd.read_csv(VERB_ROOTS_PATH, keep_default_na=False)
    if return_type == pd.DataFrame:
        return verbs_df
    return verbs_df.to_dict(orient='records')

@output_cache(os.path.dirname(__file__))
def get_verb_w_extensions_df():
    """
    Returns:
        all_verbs_with_extensions_df: pd.DataFrame with columns
        - 'root': derived stem with extensions
        - 'gloss': gloss of the base verb
        - 'fv': FV class of the derived stem
    """
    new_dfs = []
    verbs_df = get_verb_root_data(return_type=pd.DataFrame)
    for fv in FV_CLASSES:
        fv_mask = verbs_df['fv']==fv
        fv_roots = verbs_df.loc[fv_mask, 'verb_root'].tolist()
        fv_glosses = verbs_df.loc[fv_mask, 'gloss'].tolist()
        for extension_seq in ALL_POSSIBLE_EXTENSION_SEQS:
            derived_stems, derived_glosses, derived_fv = get_derived_stem_and_fv(
                base_stem=fv_roots,
                gloss=fv_glosses,
                fv=fv,
                extension_seq=extension_seq
            )
            df_for_extension_seq = pd.DataFrame({
                'verb_root': derived_stems,
                'gloss': derived_glosses,
                'fv': [derived_fv]*len(derived_stems),
            })
            new_dfs.append(df_for_extension_seq)
    all_verbs_with_extensions_df = pd.concat(new_dfs, ignore_index=True)
    return all_verbs_with_extensions_df

def get_all_verb_data(
    return_type: Union[list, pd.DataFrame]=list
) -> Union[pd.DataFrame, List[Dict[str, str]]]:
    verbs_df = pd.read_csv(VERB_ROOTS_PATH, keep_default_na=False)
    verbs_with_extensions_df = get_verb_w_extensions_df()
    all_verbs_df = pd.concat([verbs_df, verbs_with_extensions_df], ignore_index=True)
    if return_type == pd.DataFrame:
        return all_verbs_df
    return all_verbs_df.to_dict(orient='records')

def get_verb_root_w_hyphen(root_no_hyphen: str) -> str:
    """
    Arguments:
        root_no_hyphen: The verb root + extension suffixes without a hyphen.
    Returns:
        The verb root with a hyphen before the extension suffixes.
    """
    if root_no_hyphen == AUX_LEMMA_STR:
        return AUX_LEMMA_STR
    all_verbs_df = get_all_verb_data(return_type=pd.DataFrame)
    no_hyphen_series = all_verbs_df['verb_root'].str.replace('-', '')
    root_mask = no_hyphen_series==root_no_hyphen
    if root_mask.sum()==0:
        raise LexemeNotFoundError(f"Root {root_no_hyphen} not found in verb lexicon.")
    if root_mask.sum()>1:
        raise LexemeNotFoundError(f"Root {root_no_hyphen} found multiple times in verb lexicon.")
    root_with_hyphen = all_verbs_df.loc[root_mask, 'verb_root'].item()
    return root_with_hyphen

def get_gloss_for_verb(verb_root: str) -> str:
    if verb_root == AUX_LEMMA_STR:
        return "aux"
    verbs_df = get_all_verb_data(return_type=pd.DataFrame)
    root_mask = verbs_df['verb_root']==verb_root
    if root_mask.sum()==0:
        raise LexemeNotFoundError(f"Root {verb_root} not found in verb lexicon.")
    if root_mask.sum()>1:
        raise LexemeNotFoundError(f"Root {verb_root} found multiple times in verb lexicon.")
    gloss = verbs_df.loc[root_mask, 'gloss'].item()
    return gloss

def get_gold_verbs() -> List[Dict[str, str]]:
    gold_verbs_df = pd.read_csv(GOLD_VERBS_PATH, keep_default_na=False)
    return gold_verbs_df.to_dict(orient='records')

def get_gold_auxs() -> List[Dict[str, str]]:
    gold_auxs_df = pd.read_csv(GOLD_AUXS_PATH, keep_default_na=False)
    return gold_auxs_df.to_dict(orient='records')

def get_gold_person_marking() -> List[Dict[str, str]]:
    gold_person_marking_df = pd.read_csv(GOLD_PERSON_MARKING_PATH, keep_default_na=False)
    return gold_person_marking_df.to_dict(orient='records')

def get_gold_derived_verbs() -> List[Dict[str, str]]:
    gold_derived_verbs_df = pd.read_csv(GOLD_VERBS_DERIVED_PATH, keep_default_na=False)
    return gold_derived_verbs_df.to_dict(orient='records')

def get_gold_paradigms() -> List[Dict[str, Any]]:
    with open(GOLD_PARADIGMS_PATH) as f:
        gold_paradigms = json.load(f)
    return gold_paradigms

def get_gold_nouns() -> List[Dict[str, str]]:
    gold_nouns_df = pd.read_csv(GOLD_NOUNS_PATH, keep_default_na=False)
    return gold_nouns_df.to_dict(orient='records')

def get_noun_lemmata(wrap_w_fsa: bool=False) -> List[str]:
    nouns_df = pd.read_csv(NOUNS_PATH, keep_default_na=False)
    lemmata = nouns_df['lemma'].tolist()
    if wrap_w_fsa:
        lemmata = [fst(lemma) for lemma in lemmata]
    return lemmata

def get_all_noun_data(
        return_type: Union[list, pd.DataFrame]=list
) -> Union[pd.DataFrame, List[Tuple[str, str]]]:
    nouns_df = pd.read_csv(NOUNS_PATH, keep_default_na=False)
    if return_type == pd.DataFrame:
        return nouns_df
    return nouns_df.to_dict(orient='records')

def get_gloss_for_noun(lemma: str) -> str:
    nouns_df = pd.read_csv(NOUNS_PATH, keep_default_na=False)
    lemma_mask = nouns_df['lemma']==lemma
    if lemma_mask.sum()==0:
        raise LexemeNotFoundError(f"Lemma {lemma} not found in noun lexicon.")
    if lemma_mask.sum()>1:
        raise LexemeNotFoundError(f"Lemma {lemma} found multiple times in noun lexicon.")
    gloss = nouns_df.loc[lemma_mask, 'gloss'].item()
    return gloss

def get_adjective_roots(wrap_w_fsa: bool=False) -> List[str]:
    adjectives_df = pd.read_csv(ADJECTIVES_PATH, keep_default_na=False)
    roots = adjectives_df['root'].tolist()
    if wrap_w_fsa:
        roots = [fst(root) for root in roots]
    return roots

def get_gloss_for_adjective(root: str) -> str:
    adjectives_df = pd.read_csv(ADJECTIVES_PATH, keep_default_na=False)
    root_mask = adjectives_df['root']==root
    if root_mask.sum()==0:
        raise LexemeNotFoundError(f"Root {root} not found in adjective lexicon.")
    if root_mask.sum()>1:
        raise LexemeNotFoundError(f"Root {root} found multiple times in adjective lexicon.")
    gloss = adjectives_df.loc[root_mask, 'gloss'].item()
    return gloss

def get_gold_adjectives() -> List[Dict[str, str]]:
    gold_adjectives_df = pd.read_csv(GOLD_ADJECTIVES_PATH, keep_default_na=False)
    return gold_adjectives_df.to_dict(orient='records')

def get_all_adjective_data(
        return_type: Union[list, pd.DataFrame]=list
) -> Union[pd.DataFrame, List[Tuple[str, str]]]:
    adjectives_df = pd.read_csv(ADJECTIVES_PATH, keep_default_na=False)
    if return_type == pd.DataFrame:
        return adjectives_df
    return adjectives_df.to_dict(orient='records')

def get_uninflected_word_data(
        return_type: Union[list, pd.DataFrame]=list
) -> Union[pd.DataFrame, List[Tuple[Any]]]:
    uninflected_words_df = pd.read_csv(UNINFLECTED_WORDS_PATH, keep_default_na=False)
    if return_type == pd.DataFrame:
        return uninflected_words_df
    return uninflected_words_df.to_dict(orient='records')

def get_pos_and_gloss_for_uninflected_word(word: str) -> Tuple[str, str]:
    uninflected_words_df = pd.read_csv(UNINFLECTED_WORDS_PATH, keep_default_na=False)
    word_mask = uninflected_words_df['word']==word
    if word_mask.sum()==0:
        raise LexemeNotFoundError(f"Word {word} not found in uninflected word lexicon.")
    if word_mask.sum()>1:
        raise LexemeNotFoundError(f"Word {word} found multiple times in uninflected word lexicon.")
    pos = uninflected_words_df.loc[word_mask, 'part_of_speech'].item()
    gloss = uninflected_words_df.loc[word_mask, 'gloss'].item()
    return pos, gloss

def get_gold_uninflected_words() -> List[Dict[str, str]]:
    gold_uninflected_words_df = pd.read_csv(GOLD_UNINFLECTED_WORDS_PATH, keep_default_na=False)
    return gold_uninflected_words_df.to_dict(orient='records')

def get_gloss_for_root(
    root: str,
    pos: Literal['verb', 'noun', 'adjective', 'uninflected'],
) -> str:
    """
    Arguments:
        root:  The root whose gloss is to be retrieved.
        pos:   The part of speech of the root. One of 'verb', 'noun',
               'adjective', or 'uninflected'.
    Returns:
        The gloss for the given root and part of speech.
    Get the gloss for a given root based on its part of speech.
    """
    if pos == 'verb':
        return get_gloss_for_verb(root)
    elif pos == 'noun':
        return get_gloss_for_noun(root)
    elif pos == 'adjective':
        return get_gloss_for_adjective(root)
    elif pos == 'uninflected':
        _, gloss = get_pos_and_gloss_for_uninflected_word(root)
        return gloss
    else:
        raise ValueError(f"Invalid part of speech: {pos}")