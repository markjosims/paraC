"""
Module for loading lexical data from .csv files
and querying word glosses, roots, etc.
"""

import os
import pandas as pd
from src.cache_decorators import output_cache
from src.constants import (
    FV_CLASSES,
    LEXICON_DIR,
    TEST_CASE_DIR,
    AUX_LEMMA_STR,
    INFLECTED_POS,
)
from src.lexicon.extension_suffixes import get_derived_stem_and_fv, ALL_POSSIBLE_EXTENSION_SEQS
from src.fst_helpers import fst
from typing import *
import pynini

"""
## Verb lexicon functions
- get_roots_for_class: Get verb roots for a given FV class.
- get_class_for_verb_root: Get FV class for a given verb root.
- get_verb_root_data: Load verb root data from CSV.
- get_verb_w_extensions_df: Get DataFrame of verbs with extensions.
- get_all_verb_data: Get all verb data including extensions.
- get_verb_root_w_hyphen: Get verb root with hyphen before extensions.
- get_gold_verbs: Load gold standard verbs for testing.
- get_gold_auxs: Load gold standard auxiliary verbs for testing.
- get_gold_person_marking: Load gold standard verb data with person marking.
- get_gold_derived_verbs: Load gold standard derived verbs for testing.
"""

def get_roots_for_class(
        fv_class: str,
        wrap_w_fsa: bool=False,
        include_extensions: bool=False
) -> List[Union[str, pynini.Fst]]:
    """
    Fetches all verb roots for a given final vowel (FV) class.

    Args:
        fv_class: string indicating a FV class
        wrap_w_fsa: bool whether to wrap each root in an FSA
        include_extensions: bool whether to include verb roots with extensions

    Returns:
        List of strings or FSAs corresponding to verb roots in the given FV class
    """
    if include_extensions:
        verbs_df = get_all_verb_data(return_type='dataframe')
    else:
        verbs_df = get_verb_root_data(return_type='dataframe')
    fv_mask = verbs_df['fv']==fv_class
    roots = verbs_df.loc[fv_mask, 'root'].str.replace('-', '').tolist()
    if wrap_w_fsa:
        roots = [fst(root) for root in roots]
    return roots

def get_class_for_verb_root(root: str) -> List[str]:
    """
    Given a verb root, finds the corresponding FV class(es).

    Arguments:
        root: The verb root whose FV class is to be retrieved.
    Returns:
        The FV class(es) for the given verb root.
    """
    all_verbs_df = get_all_verb_data(return_type='dataframe')
    root_mask = all_verbs_df['root']==root
    if root_mask.sum()==0:
        raise KeyError(f"Root {root} not found in verb lexicon.")
    fv_class_list = all_verbs_df.loc[root_mask, 'fv'].tolist()
    return fv_class_list

def get_verb_root_data(
        return_type: Literal['list', 'dataframe']='list'
) -> Union[pd.DataFrame, List[Dict[str, str]]]:
    verb_path = os.path.join(LEXICON_DIR, 'verbs.csv')
    verbs_df = pd.read_csv(verb_path, keep_default_na=False)
    if return_type == 'dataframe':
        return verbs_df
    return verbs_df.to_dict(orient='records')

@output_cache(os.path.dirname(__file__))
def get_verb_w_extensions_df():
    """
    Generates a dataframe of all verb roots with possible extension suffixes.

    Returns:
        all_verbs_with_extensions_df: pd.DataFrame with columns
        - 'root': derived stem with extensions
        - 'gloss': gloss of the base verb
        - 'fv': FV class of the derived stem
    """
    new_dfs = []
    verbs_df = get_verb_root_data(return_type='dataframe')

    # since extensions may change shape as a function of the base verb's FV class,
    # we need to iterate through each FV class separately
    for fv in FV_CLASSES:
        fv_mask = verbs_df['fv']==fv
        fv_roots = verbs_df.loc[fv_mask, 'root'].tolist()
        fv_glosses = verbs_df.loc[fv_mask, 'gloss'].tolist()
        # for each possible extension sequence, generate the derived stems/glosses/FV
        for extension_seq in ALL_POSSIBLE_EXTENSION_SEQS:
            derived_stems, derived_glosses, derived_fv = get_derived_stem_and_fv(
                base_stem=fv_roots,
                gloss=fv_glosses,
                fv=fv,
                extension_seq=extension_seq
            )
            df_for_extension_seq = pd.DataFrame({
                'root': derived_stems,
                'gloss': derived_glosses,
                'fv': [derived_fv]*len(derived_stems),
            })
            new_dfs.append(df_for_extension_seq)
    all_verbs_with_extensions_df = pd.concat(new_dfs, ignore_index=True)
    return all_verbs_with_extensions_df

def get_all_verb_data(
    return_type: Literal['list', 'dataframe']='list'
) -> Union[pd.DataFrame, List[Dict[str, str]]]:
    """
    Creates a dataframe containing all verb data, including
    both verb roots and verbs with extension suffixes.

    Args:
        return_type: set to 'dataframe' to return a pandas DataFrame,
                     or 'list' to return a list of dictionaries.

    Returns:
        All verb data including those with extension suffixes.

    """
    verbs_df = get_verb_root_data(return_type='dataframe')
    verbs_with_extensions_df = get_verb_w_extensions_df()
    all_verbs_df = pd.concat([verbs_df, verbs_with_extensions_df], ignore_index=True)
    if return_type == 'dataframe':
        return all_verbs_df
    return all_verbs_df.to_dict(orient='records')

def get_verb_root_w_hyphen(root_no_hyphen: str, fv: Optional[str]=None) -> List[str]:
    """
    Given a verb root without a hyphen before extension suffixes,
    finds the corresponding verb root(s) with the hyphen.

    Arguments:
        root_no_hyphen: The verb root + extension suffixes without a hyphen.
        fv: Optional final vowel class to further filter results.
    Returns:
        The verb root with a hyphen before the extension suffixes.
    """
    if root_no_hyphen == AUX_LEMMA_STR:
        return [AUX_LEMMA_STR]
    all_verbs_df = get_all_verb_data(return_type='dataframe')
    no_hyphen_series = all_verbs_df['root'].str.replace('-', '')
    root_mask = no_hyphen_series==root_no_hyphen
    if fv is not None:
        fv_mask = all_verbs_df['fv']==fv
        root_mask = root_mask & fv_mask
    if root_mask.sum()==0:
        raise KeyError(f"Root {root_no_hyphen} not found in verb lexicon.")
    root_with_hyphen = all_verbs_df.loc[root_mask, 'root'].tolist()
    return root_with_hyphen

def get_gold_verbs() -> List[Dict[str, str]]:
    """
    Loads gold standard verbs from a CSV file for testing purposes.
    Returns:
        List of dictionaries representing gold standard verbs.
    """
    gold_verbs_path = os.path.join(TEST_CASE_DIR, 'gold_verbs.csv')
    gold_verbs_df = pd.read_csv(gold_verbs_path, keep_default_na=False)
    return gold_verbs_df.to_dict(orient='records')

def get_gold_auxs() -> List[Dict[str, str]]:
    """
    Loads gold standard auxiliary verbs from a CSV file for testing purposes.
    Returns:
        List of dictionaries representing gold standard auxiliary verbs.
    """
    gold_aux_path = os.path.join(TEST_CASE_DIR, 'gold_auxs.csv')
    gold_auxs_df = pd.read_csv(gold_aux_path, keep_default_na=False)
    return gold_auxs_df.to_dict(orient='records')

def get_gold_person_marking() -> List[Dict[str, str]]:
    """
    Loads gold standard verb data with person marking from a CSV file
    for testing purposes.
    Returns:
        List of dictionaries representing gold standard verb data
        with person marking.

    """
    gold_person_marking_path = os.path.join(TEST_CASE_DIR, 'gold_person_marking.csv')
    gold_person_marking_df = pd.read_csv(gold_person_marking_path, keep_default_na=False)
    return gold_person_marking_df.to_dict(orient='records')

def get_gold_derived_verbs() -> List[Dict[str, str]]:
    """
    Loads gold standard derived verbs from a CSV file for testing purposes.
    Returns:
        List of dictionaries representing gold standard derived verbs.
    """
    gold_derived_verbs_path = os.path.join(TEST_CASE_DIR, 'gold_verbs_derived.csv')
    gold_derived_verbs_df = pd.read_csv(gold_derived_verbs_path, keep_default_na=False)
    return gold_derived_verbs_df.to_dict(orient='records')

"""
## Noun lexicon functions
- get_noun_roots: Get list of noun roots.
- get_all_noun_data: Get all noun data from CSV.
- get_gold_nouns: Load gold standard nouns for testing.
"""

def get_gold_nouns() -> List[Dict[str, str]]:
    """
    Loads gold standard nouns from a CSV file for testing purposes.
    Returns:
        List of dictionaries representing gold standard nouns.
    """
    gold_nouns_path = os.path.join(TEST_CASE_DIR, 'gold_nouns.csv')
    gold_nouns_df = pd.read_csv(gold_nouns_path, keep_default_na=False)
    return gold_nouns_df.to_dict(orient='records')

def get_noun_roots(wrap_w_fsa: bool=False) -> List[str]:
    """
    Fetches all noun roots from the noun lexicon.
    Args:
        wrap_w_fsa: bool whether to wrap each lemma in an FSA

    Returns:
        List of strings or FSAs corresponding to noun lemmata

    """
    nouns_df = get_all_noun_data(return_type='dataframe')
    roots = nouns_df['root'].tolist()
    if wrap_w_fsa:
        roots = [fst(lemma) for lemma in roots]
    return roots

def get_all_noun_data(
        return_type: Literal['list', 'dataframe']='list'
) -> Union[pd.DataFrame, List[Dict[str, str]]]:
    """
    Loads all noun data from the noun lexicon CSV file.

    Args:
        return_type: set to 'dataframe' to return a pandas DataFrame,
                     or 'list' to return a list of dictionaries.

    Returns:
        pd.DataFrame or list of dictionaries containing noun data.
    """
    nouns_path = os.path.join(LEXICON_DIR, 'nouns.csv')
    nouns_df = pd.read_csv(nouns_path, keep_default_na=False)
    if return_type == 'dataframe':
        return nouns_df
    return nouns_df.to_dict(orient='records')

"""
## Adjective lexicon functions
- get_adjective_roots: Get list of adjective roots.
- get_all_adjective_data: Get all adjective data from CSV.
- get_gold_adjectives: Load gold standard adjectives for testing.
"""

def get_adjective_roots(wrap_w_fsa: bool=False) -> List[str]:
    """
    Fetches all adjective roots from the adjective lexicon.
    Args:
        wrap_w_fsa: bool whether to wrap each root in an FSA

    Returns:
        List of strings or FSAs corresponding to adjective roots
    """
    adjectives_df = get_all_adjective_data(return_type='dataframe')
    roots = adjectives_df['root'].tolist()
    if wrap_w_fsa:
        roots = [fst(root) for root in roots]
    return roots

def get_all_adjective_data(
        return_type: Literal['list', 'dataframe']='list'
) -> Union[pd.DataFrame, List[Dict[str, str]]]:
    """
    Loads all adjective data from the adjective lexicon CSV file.
    Args:
        return_type: set to 'dataframe' to return a pandas DataFrame,
                     or 'list' to return a list of dictionaries.

    Returns:
        pd.DataFrame or list of dictionaries containing adjective data.
    """
    adjectives_path = os.path.join(LEXICON_DIR, 'adjectives.csv')
    adjectives_df = pd.read_csv(adjectives_path, keep_default_na=False)
    if return_type == 'dataframe':
        return adjectives_df
    return adjectives_df.to_dict(orient='records')

def get_gold_adjectives() -> List[Dict[str, str]]:
    """
    Loads gold standard adjectives from a CSV file for testing purposes.

    Returns:
        List of dictionaries representing gold standard adjectives.

    """
    gold_adjectives_path = os.path.join(TEST_CASE_DIR, 'gold_adjectives.csv')
    gold_adjectives_df = pd.read_csv(gold_adjectives_path, keep_default_na=False)
    return gold_adjectives_df.to_dict(orient='records')

"""
## Uninflected word lexicon functions
- get_uninflected_word_data: Get uninflected word data from CSV.
- get_gold_uninflected_words: Load gold standard uninflected words for testing.
"""

def get_uninflected_word_data(
        return_type: Literal['list', 'dataframe']='list'
) -> Union[pd.DataFrame, List[Dict[str, str]]]:
    """
    Loads uninflected word data from the uninflected words CSV file.
    Args:
        return_type: set to 'dataframe' to return a pandas DataFrame,
                     or 'list' to return a list of dictionaries.

    Returns:
        pd.DataFrame or list of dictionaries containing uninflected word data.
    """
    uninflected_words_path = os.path.join(LEXICON_DIR, 'uninflected_words.csv')
    uninflected_words_df = pd.read_csv(uninflected_words_path, keep_default_na=False)
    if return_type == 'dataframe':
        return uninflected_words_df
    return uninflected_words_df.to_dict(orient='records')

def get_gold_uninflected_words() -> List[Dict[str, str]]:
    """
    Loads gold standard uninflected words from a CSV file for testing purposes.
    Returns:
        List of dictionaries representing gold standard uninflected words.
    """
    gold_uninflected_words_path = os.path.join(TEST_CASE_DIR, 'gold_uninflected_words.csv')
    gold_uninflected_words_df = pd.read_csv(gold_uninflected_words_path, keep_default_na=False)
    return gold_uninflected_words_df.to_dict(orient='records')

"""
## Global lexicon functions

"""

def get_all_lexical_data(
    return_type: Literal['list', 'dataframe']='list'
) -> Union[pd.DataFrame, List[Dict[str, str]]]:
    """
    Combines all lexical data from verbs, nouns, adjectives,
    and uninflected words into a single dataset.

    Args:
        return_type: set to 'dataframe' to return a pandas DataFrame,
                     or 'list' to return a list of dictionaries.
    Returns:
        Combined lexical data as a DataFrame or list of dictionaries.
    """
    data_fetchers = {
        'verb': get_all_verb_data,
        'noun': get_all_noun_data,
        'adjective': get_all_adjective_data,
        'uninflected': get_uninflected_word_data,
    }

    df_list = []
    for key, fetcher in data_fetchers.items():
        df = fetcher(return_type='dataframe')
        if key != 'uninflected':
            df['part_of_speech'] = key
        df_list.append(df)

    all_lexical_df = pd.concat(
        df_list,
        ignore_index=True,
    )
    if return_type == 'dataframe':
        return all_lexical_df
    return all_lexical_df.to_dict(orient='records')

def get_gloss_for_root(
    root: str,
    part_of_speech: Optional[Literal['verb', 'noun', 'adjective', 'uninflected']] = None,
    return_pos: bool=False,
) -> List[Union[str, Tuple[str, str]]]:
    """
    Get the gloss for a given root based on its part of speech.

    Arguments:
        root:  The root whose gloss is to be retrieved.
        part_of_speech:   The part of speech of the root. One of 'verb', 'noun',
               'adjective', or 'uninflected'.
        return_pos: Whether to return the part of speech along with the gloss.
    Returns:
        The gloss for the given root and part of speech.
    """
    if root == AUX_LEMMA_STR:
        if return_pos:
            return [('aux', 'aux')]
        return ['aux']

    all_lexical_data = get_all_lexical_data(return_type='dataframe')
    root_mask = all_lexical_data['root']==root
    if part_of_speech == 'uninflected':
        pos_mask = ~all_lexical_data['part_of_speech'].isin(INFLECTED_POS)
        root_mask = root_mask & pos_mask
    elif part_of_speech is not None:
        pos_mask = all_lexical_data['part_of_speech']==part_of_speech
        root_mask = root_mask & pos_mask
    if root_mask.sum()==0:
        if part_of_speech is not None:
            raise KeyError(f"Root {root} with part of speech {part_of_speech} not found in lexicon.")
        raise KeyError(f"Root {root} not found in lexicon.")
    gloss_list = all_lexical_data.loc[root_mask, 'gloss'].tolist()
    if return_pos:
        pos_list = all_lexical_data.loc[root_mask, 'part_of_speech'].tolist()
        return list(zip(gloss_list, pos_list))
    return gloss_list

def get_part_of_speech_for_root(root: str) -> List[str]:
    """
    Get the part(s) of speech for a given root.

    Arguments:
        root: The root whose part(s) of speech is to be retrieved.
    Returns:
        The part(s) of speech for the given root.
    """
    all_lexical_data = get_all_lexical_data(return_type='dataframe')
    root_mask = all_lexical_data['root']==root
    if root_mask.sum()==0:
        raise KeyError(f"Root {root} not found in lexicon.")
    pos_list = all_lexical_data.loc[root_mask, 'part_of_speech'].tolist()
    return pos_list

def get_root_for_gloss(
    gloss: str,
    part_of_speech: Optional[Literal['verb', 'noun', 'adjective', 'uninflected']] = None,
    return_pos: bool=False,
) -> List[Union[str, Tuple[str, str]]]:
    """
    Get the root for a given gloss based on its part of speech.

    Arguments:
        gloss: The gloss whose root is to be retrieved.
        part_of_speech:   The part of speech of the gloss. One of 'verb', 'noun',
               'adjective', or 'uninflected'.
        return_pos: Whether to return the part of speech along with the root.
    Returns:
        The root for the given gloss and part of speech.
    """
    if gloss == 'aux':
        if return_pos:
            return [(AUX_LEMMA_STR, 'aux')]
        return [AUX_LEMMA_STR]
    all_lexical_data = get_all_lexical_data(return_type='dataframe')
    gloss_mask = all_lexical_data['gloss']==gloss
    if part_of_speech == 'uninflected':
        pos_mask = ~all_lexical_data['part_of_speech'].isin(INFLECTED_POS)
        gloss_mask = gloss_mask & pos_mask
    elif part_of_speech is not None:
        pos_mask = all_lexical_data['part_of_speech']==part_of_speech
        gloss_mask = gloss_mask & pos_mask
    if gloss_mask.sum()==0:
        if part_of_speech is not None:
            raise KeyError(f"Gloss {gloss} with part of speech {part_of_speech} not found in lexicon.")
        raise KeyError(f"Gloss {gloss} not found in lexicon.")
    root_list = all_lexical_data.loc[gloss_mask, 'root'].tolist()
    if return_pos:
        pos_list = all_lexical_data.loc[gloss_mask, 'part_of_speech'].tolist()
        return list(zip(root_list, pos_list))
    return root_list