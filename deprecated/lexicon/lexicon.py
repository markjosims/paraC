"""
Module for loading lexical data from .csv files
and querying word glosses, roots, etc.
"""

import os
import pandas as pd
from src.decorators import output_cache
from src.constants import (
    FV_CLASSES,
    LEXICON_DIR,
    TEST_CASE_DIR,
    AUX_LEMMA_STR,
    INFLECTED_POS,
    POS_GROUPS,
)
from src.lexicon.extension_suffixes import get_derived_stem_and_fv, ALL_POSSIBLE_EXTENSION_SEQS
from src.fst_helpers import fst
from typing import *
import pynini
from glob import glob
import unicodedata
from io import StringIO

"""
## Data loading functions
"""

def get_macro_pos(
        micro_pos: str
) -> str:
    """
    Given a specific part of speech, returns the corresponding
    'macro' part of speech (i.e., the name of the CSV file
    from which the data is loaded).

    Args:
        micro_pos: The specific part of speech.
    Returns:
        The macro part of speech corresponding to the specific part of speech.
    """
    for pos_group_name, pos_for_group in POS_GROUPS.items():
        if micro_pos in pos_for_group:
            return pos_group_name
    return micro_pos

def get_pos_mask(
        df: pd.DataFrame,
        part_of_speech: str
) -> pd.Series:
    """
    Returns a boolean mask for the given part of speech. This allows users to
    specify either a 'macro' part of speech (e.g., 'nominal', 'adnominal',
    'uninflected') or a specific part of speech (e.g. 'noun', 'adverb')
    with the same function.

    Args:
        df: pandas DataFrame containing lexical data
        part_of_speech: The part of speech to create a mask for.
                        For the two 'macro' parts of speech ('nominal' and 'adnominal'),
                        either the macro name (corresponding to the csv filestem) or
                        one of the included parts of speech may be used.
    Returns:
        A pandas Series boolean mask for the specified part of speech.
    """
    if part_of_speech in POS_GROUPS:
        pos_list = POS_GROUPS[part_of_speech]
        pos_mask = df['part_of_speech'].isin(pos_list)
    else:
        pos_mask = df['part_of_speech']==part_of_speech
    return pos_mask

def load_csv(
    csv_path: str
) -> pd.DataFrame:
    """
    Wraps `pandas.read_csv`, performs NFKD normalization on file
    and explodes the `root` column into pronunciation variants.
    """

    # perform NFKD normalization on file contents
    with open(csv_path, 'r', encoding='utf8') as f:
        text = f.read()
    text_norm = unicodedata.normalize('NFKD', text)

    text_buffer = StringIO(text_norm)
    df = pd.read_csv(text_buffer, keep_default_na=False)

    # split pronunciation variants
    df['root'] = df['root'].str.split(' ')
    df = df.explode('root')
    return df

def load_lexical_data(
        part_of_speech: str,
) -> pd.DataFrame:
    """
    Loads lexical data from a CSV file based on the specified part of speech.

    Args:
        part_of_speech: The part of speech to load data for.
                        For the two 'macro' parts of speech ('nominal' and 'adnominal'),
                        either the macro name (corresponding to the csv filestem) or
                        one of the included parts of speech may be used.
    Returns:
        A pandas DataFrame containing the lexical data for the specified part of speech.
    """
    macro_pos = get_macro_pos(part_of_speech)
    csv_path = os.path.join(LEXICON_DIR, f"{macro_pos}.csv")
    lexical_df = load_csv(csv_path)
    if macro_pos != part_of_speech:
        # user specified 'micro' part of speech; filter accordingly
        pos_mask = get_pos_mask(lexical_df, part_of_speech)
        lexical_df = lexical_df.loc[pos_mask].reset_index(drop=True)
    return lexical_df

def load_test_case_data(
        test_case_filename: str
) -> List[Dict[str, str]]:
    """
    Loads test case data from a CSV file.

    Args:
        test_case_filename: The filename of the test case CSV file.
    Returns:
        A list of dictionaries representing the test case data.
    """
    csv_path = os.path.join(TEST_CASE_DIR, f"{test_case_filename}.csv")
    test_case_df = load_csv(csv_path)
    return test_case_df.to_dict(orient='records')

"""
## Verb lexicon functions
- get_roots_for_class: Get verb roots for a given FV class.
- get_class_for_verb_root: Get FV class for a given verb root.
- get_verb_w_extensions_df: Get DataFrame of verbs with extensions.
- get_all_verb_data: Get all verb data including extensions.
- get_verb_root_w_hyphen: Get verb root with hyphen before extensions.
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
        verbs_df = get_all_verb_data()
    else:
        verbs_df = load_lexical_data(part_of_speech='verb')
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
    all_verbs_df = get_all_verb_data()
    root_mask = all_verbs_df['root']==root
    if root_mask.sum()==0:
        raise KeyError(f"Root {root} not found in verb lexicon.")
    fv_class_list = all_verbs_df.loc[root_mask, 'fv'].tolist()
    return fv_class_list

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
    verbs_df = load_lexical_data(part_of_speech='verb')

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

def get_all_verb_data() -> pd.DataFrame:
    """
    Creates a dataframe containing all verb data, including
    both verb roots and verbs with extension suffixes.

    Args:
        return_type: set to 'dataframe' to return a pandas DataFrame,
                     or 'list' to return a list of dictionaries.

    Returns:
        All verb data including those with extension suffixes.

    """
    verbs_df = load_lexical_data(part_of_speech='verb')
    verbs_with_extensions_df = get_verb_w_extensions_df()
    all_verbs_df = pd.concat([verbs_df, verbs_with_extensions_df], ignore_index=True)
    return all_verbs_df

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
    all_verbs_df = get_all_verb_data()
    no_hyphen_series = all_verbs_df['root'].str.replace('-', '')
    root_mask = no_hyphen_series==root_no_hyphen
    if fv is not None:
        fv_mask = all_verbs_df['fv']==fv
        root_mask = root_mask & fv_mask
    if root_mask.sum()==0:
        raise KeyError(f"Root {root_no_hyphen} not found in verb lexicon.")
    root_with_hyphen = all_verbs_df.loc[root_mask, 'root'].tolist()
    return root_with_hyphen


"""
## Global lexicon functions
"""

@output_cache(LEXICON_DIR)
def get_all_lexical_data() -> pd.DataFrame:
    """
    Combines all lexical data from verbs, nouns, adjectives,
    and uninflected words into a single dataset.

    Args:
        return_type: set to 'dataframe' to return a pandas DataFrame,
                     or 'list' to return a list of dictionaries.
    Returns:
        Combined lexical data as a DataFrame or list of dictionaries.
    """
    csv_paths = glob(os.path.join(LEXICON_DIR, '*.csv'))

    df_list = []
    for csv_path in csv_paths:
        csv_stem = os.path.basename(csv_path)
        csv_stem = os.path.splitext(csv_stem)[0]
        
        # verbs are a special case, since extended forms are built dynamically
        if csv_stem == 'verb':
            df = get_all_verb_data()
        else:
            df = load_csv(csv_path)

        # add part_of_speech column if not already present
        # either filename indicates part of speech, or (for data files
        # with multiple parts of speech) the column is already present
        if 'part_of_speech' not in df.columns:
            df['part_of_speech'] = csv_stem

        df_list.append(df)

    all_lexical_df = pd.concat(
        df_list,
        ignore_index=True,
    )
    return all_lexical_df

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

    all_lexical_data = get_all_lexical_data()
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
    all_lexical_data = get_all_lexical_data()
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
    all_lexical_data = get_all_lexical_data()
    gloss_mask = all_lexical_data['gloss']==gloss

    # optionally filter by part of speech
    if part_of_speech is not None:
        pos_mask = get_pos_mask(all_lexical_data, part_of_speech)
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