import pynini

from typing import *
from src.decorators import fst_cache, output_cache
from src.fst_helpers import *
from src.constants import (
    INSERT, DELETE, SUBSTITUTE,
    DEFAULT_INSERT_COST, DEFAULT_DELETE_COST, DEFAULT_SUBSTITUTE_COST,
    DEFAULT_EDIT_BOUND, SENTENCE_DIR,
)
from src.lexicon.phonology import (
    SIGMA, INSERTION_COSTS, DELETION_COSTS, SUBSTITUTION_COSTS,
    INSERT_HYPHEN_RULE
)
from src.parser import get_main_parser, parse_is_root, parse_word
import os
from unidecode import unidecode
import pandas as pd

"""
## Non-FST search functions 
"""

def search_corpus(
        query,
        query_type: Literal['tira', 'en'] = 'tira',
        whole_word=False
    ) -> List[Dict[str, str]]:
    """
    Search sentences.csv for occurrences of the given word.
    To allow for (very simple) fuzzy matching, the word is first
    normalized by removing diacritics and converting to lowercase,
    and matched against sentences that have undergone the same normalization.
    """
    query = unidecode(query).lower()
    corpus_path = os.path.join(SENTENCE_DIR, 'sentences.csv')
    df = pd.read_csv(corpus_path, keep_default_na=False)
    if query_type == 'tira':
        normalized_sentence = df['text'].apply(unidecode).str.lower()
    elif query_type == 'en':
        normalized_sentence = df['translation'].apply(unidecode).str.lower()
    else:
        raise ValueError("query_type must be one of 'tira' or 'en'")

    if whole_word:
        split_sentences = normalized_sentence.str.split(' ')
        matching_rows = df[split_sentences.apply(lambda x: query in x)]
    else:
        matching_rows = df[normalized_sentence.str.contains(query, na=False)]
    
    return_cols = ['text', 'translation', 'gloss']
    return matching_rows[return_cols].to_dict(orient='records') # type: ignore
    

def search_parse_csv(
    root: Optional[str] = None,
    features: Union[str, List[str]] = [],
    parse_csv_path: str = os.path.join(SENTENCE_DIR, 'parses.csv'),
    max_cost: float = float('inf'),
) -> List[Dict[str, str]]:
    """
    Search a CSV file containing parses for entries matching a given lemma and features.
    For the moment 'feature' is a simple substring match against the gloss field.

    Arguments:
        root:               Optional[str], root to search for
        features:           Features that must be present in the parse, passed as a comma-separated
                            string or list of strings
        parse_csv_path:     str, path to CSV file containing parses
        max_cost:           float, maximum cost allowed between the root and the parse's root
    Returns:
        List[Dict[str, str]] containing matching parses
    """
    df = pd.read_csv(parse_csv_path, keep_default_na=False)
    matching_rows = df['weight'] <= max_cost
    if root:
        matching_rows &= df['root']==root

    lowercase_gloss = df['gloss'].str.lower()

    if type(features) is str:
        features = features.split(',')

    for feature in features:
        feature = feature.strip().lower()
        matching_rows &= lowercase_gloss.str.contains(feature, na=False)
    
    columns = [
        'original_str', 'word', 'updated_str', 'gloss', 'root',
        'weight', 'sentence', 'translation'
    ]

    matching_df = df[matching_rows][columns]
    return matching_df.to_dict(orient='records')  # type: ignore

# ----------------------------------- #
# functions for building search graph #
# ----------------------------------- #

def get_searchable_lexicon(
        lexicon: Union[List[str], pynini.FstLike],
        **edit_factor_kwargs,
    ) -> Tuple[pynini.Fst, pynini.Fst]:
    """
    Arguments:
        lexicon:                List of strings or Pynini FST representing lexicon to search
        edit_factor_kwargs:     Arguments for `get_edit_factors`
    Returns:
        (left_factor, searchable_lexicon):    FST to compile with queries; pre-compiled FST right_factor@lexicon

    Wraps `get_edit_factors` and compiles right factor with lexicon.
    """
    if type(lexicon) is list:
        lexicon = fst(lexicon)
    left_factor, right_factor = get_edit_factors(**edit_factor_kwargs)
    searchable_lexicon = right_factor@lexicon
    searchable_lexicon.optimize().arcsort()
    return left_factor, searchable_lexicon

@fst_cache(os.path.dirname(__file__), num_fst=2)
def get_searchable_main_parser(**edit_factor_kwargs) -> Tuple[pynini.Fst, pynini.Fst]:
    """
    Arguments:
        edit_factor_kwargs:     Arguments for `get_edit_factors`
    Returns:
        (left_factor, searchable_lexicon):    FST to compile with queries; pre-compiled FST right_factor@lexicon

    Wraps `get_edit_factors` and compiles right factor with main parser lexicon.
    """
    main_lemmatizer, _, _ = get_main_parser()
    left_factor, right_factor = get_edit_factors(**edit_factor_kwargs)
    lexicon = pynini.project(main_lemmatizer, 'input')
    searchable_lexicon = right_factor@lexicon
    searchable_lexicon.optimize().arcsort()
    return left_factor, searchable_lexicon

@output_cache(__file__)
def get_edit_factors(
        insertions: List[Tuple[pynini.FstLike, pynini.WeightLike]]=INSERTION_COSTS,
        substitutions: List[Tuple[pynini.FstLike, pynini.FstLike, pynini.WeightLike]]=SUBSTITUTION_COSTS,
        deletions: List[Tuple[pynini.FstLike, pynini.WeightLike]]=DELETION_COSTS,
        sigma: pynini.FstLike=SIGMA,
        insert_cost: float=DEFAULT_INSERT_COST,
        sub_cost: float=DEFAULT_SUBSTITUTE_COST,
        delete_cost: float=DEFAULT_DELETE_COST,
        bound: Optional[int]=DEFAULT_EDIT_BOUND,
    ) -> Tuple[pynini.Fst, pynini.Fst]:
    """
    Arguments:
        insertions:     List of couples (insertion_element, insertion_cost) where `insertion_element`
                        is a str or FST and `insertion_cost` is a weight for inserting the element
        substitutions:  List of triples (sub_intab, sub_outtab, sub_cost) where `sub_intab` and `sub_outtab`
                        is the pair of strs or FSTs to substitute and `sub_cost` is a weight associated with
                        the substitution. Note `sub_intab` refers to elements in the **query** and `sub_outtab`
                        to elements in the **lexicon**.
        deletions:      List of couples (deletion_element, deletion_cost) where `deletion_element` is a str
                        or FST and `deletion_cost` is a weight for deleting the element
        sigma:          FST representing the alphabet of the lexicon.
        insert_cost:    Default cost for inserting any element not specified in `insertions`.
        delete_cost:    Default cost for deleting any element not specified in `deletions`.
        sub_cost:       Default cost for substituting any element not specified in `substitutions`.
        bound:          Integer indicating the number of edits allowed when searching. Defaults to `DEFAULT_EDIT_BOUND`.
                        Pass `None` for unbounded edits.

    Returns:
        (left_factor, right_factor):    FSTs for the left and right factors.

    Compiles FSTs representing an edit transducer allowing for custom weights for particular edits, as specified in `insertions`,
    `deletions` and `substitutions`. Returns left and right factors for searching. Usage for searching is `query@left_factor@right_factor@lexicon`.
    """
    insert_graph_left, insert_graph_right = _get_insertion_graph(insertions, insert_cost, sigma)
    delete_graph_left, delete_graph_right = _get_deletion_graph(deletions, delete_cost, sigma)
    sub_graph_left, sub_graph_right = _get_substitution_graph(substitutions, sub_cost, sigma)

    edit_graph_left = pynini.union(insert_graph_left, delete_graph_left, sub_graph_left).optimize().arcsort()
    edit_graph_right = pynini.union(insert_graph_right, delete_graph_right, sub_graph_right).optimize().arcsort()
    
    left_factor = _compose_edit_graph_w_sigma(edit_graph_left, sigma, bound)
    right_factor = _compose_edit_graph_w_sigma(edit_graph_right, sigma, bound)

    left_factor.optimize().arcsort()
    right_factor.optimize().arcsort()

    return left_factor, right_factor

def _compose_edit_graph_w_sigma(
        edit_graph: pynini.Fst,
        sigma: pynini.Fst,
        bound: Optional[int]=None,
    ) -> pynini.Fst:
    """
    Composes edit graph with the alphabet `sigma`. If `bound` is passed,
    composes cyclically once for each bound.
    """
    if bound:
        sigma_star = pynini.closure(sigma)
        composed_factor = sigma_star.copy()
        for _ in range(bound):
            composed_factor.concat(edit_graph.ques).concat(sigma_star)
    else:
        composed_factor = edit_graph.union(sigma).closure()
    composed_factor=composed_factor.optimize().arcsort()
    return composed_factor

def _get_insertion_graph(
        insertions: List[Tuple[str, pynini.WeightLike]],
        insert_cost: pynini.WeightLike,
        sigma: pynini.Fst,
    ) -> pynini.Fst:
    """
    Arguments:
        insertions:     list of tuples of strings and custom insert weights per string
        insert_cost:    default weight for insertion
        sigma:          FSA of alphabet
    Returns:
        insert_graph_left, insert_graph_right: left and right factors for calculating insert costs
    
    Builds left factor as a simple FST mapping epsilon to the insertion symbol, weight of semiring Zero.
    Builds right factor as a map of insertion symbol to each element on the alphabet with a weight
    as defined by `insertions` where applicable, else `insert_cost`.
    """
    insert_inputs = fst([insert[0] for insert in insertions])
    sigma_except_custom = sigma-insert_inputs
    sigma_except_custom_weighted = sigma_except_custom + fst('', weight=insert_cost)
    insert_symbol = f"[{INSERT}]"
    insert_graph_left = insert_fst(insert_symbol)
    insert_graph_right = fst(insert_symbol, sigma_except_custom_weighted)
    for (insert_str, cost) in insertions:
        insertion_fst = fst(insert_symbol, insert_str, cost)
        insert_graph_right=insert_graph_right|insertion_fst
    return insert_graph_left, insert_graph_right

def _get_deletion_graph(
        deletions: List[Tuple[str, pynini.WeightLike]],
        delete_cost: pynini.WeightLike,
        sigma: pynini.Fst,
    ) -> pynini.Fst:
    """
    Arguments:
        deletions: list of tuples of strings and custom deletion weights per string
        delete_cost: default weight for deletion
        sigma: FSA of alphabet
    Returns:
        delete_graph_left, delete_graph_right: left and right factors for calculating deletion costs

    Builds the left factor as an FST mapping each element on the alphabet to the deletion symbol with
    weight defined by `deletions` if applicable else `delete_cost`.
    Builds the right factor as a simple FST mapping the deletion symbol to epsilon, weight semiring Zero.
    """
    delete_inputs = fst([delete[0] for delete in deletions])
    sigma_except_custom = sigma-delete_inputs
    delete_symbol = f"[{DELETE}]"
    delete_graph_left = fst(sigma_except_custom, delete_symbol, weight=delete_cost)
    for (delete_str, cost) in deletions:
        deletion_fst = fst(delete_str, delete_symbol, cost)
        delete_graph_left=delete_graph_left|deletion_fst

    delete_graph_right = delete_fst(delete_symbol)
    return delete_graph_left, delete_graph_right
    
def _get_substitution_graph(
        substitutions: List[Tuple[str, pynini.WeightLike]],
        sub_cost: pynini.WeightLike,
        sigma: pynini.Fst,
    ) -> pynini.Fst:
    """
    Arguments:
        substitutions: list of tuples of strings and custom sub weights per string, e.g.
        sub_cost: default weight for substitution
        sigma: FSA of alphabet

    Returns:
        sub_graph_left, sub_graph_right: left and right factors for calculating substitution costs

    Builds the left factor as an FST mapping each element on the alphabet to the substitution symbol,
    where the default symbol is used for any pair of elements not specified in `substitutions`.
    Else, for each intab in `substitutions` map to a sequence of the substitution symbol and the intab.
    Builds the right factor as an FST mapping the default symbol to any element on the alphabet and each
    special symbol to its appropriate outtab, i.e.:

        Left factor                     Right factor
        \sigma  --> [<substitution>]    --> \sigma
        d       --> [<substitution>d]   --> e
        f       --> [<substitution>f]   --> g

    If d>e and f>g are specifically defined in the custom substitutions.

    Weight values from `substitutions` or `sub_cost` are used for the left factor.
    Arcs on the right factor use semiring Zero.
    """
    intabs = [sub[0] for sub in substitutions]
    intab_fst = fst(intabs)
    sigma_except_intabs = sigma-intab_fst
    sub_symbol = f"[{SUBSTITUTE}]"
    sub_acceptor = fst(sub_symbol)
    sub_graph_left = fst(sigma_except_intabs, sub_acceptor)
    sub_graph_right = fst(sub_acceptor, sigma, weight=sub_cost)
    
    # cache all intabs that have been accounted for
    # can't call `set` on intabs since pynini.Fst in unhashable
    used_intabs = []
    for i, intab in enumerate(intabs):
        if intab in used_intabs:
            continue
        intab_sub_symbol = f"[{SUBSTITUTE}{i}]"
        subs_w_intab = [sub for sub in substitutions if sub[0]==intab]
        
        outtabs_for_element = [sub[1] for sub in subs_w_intab]
        outtabs_fst = fst(outtabs_for_element)
        remaining_outtabs = sigma-outtabs_fst
        sub_fst_left = fst(intab, intab_sub_symbol)
        sub_graph_left=sub_graph_left|sub_fst_left

        sub_fst_right = fst(intab_sub_symbol, remaining_outtabs, sub_cost)
        sub_graph_right = sub_graph_right|sub_fst_right

        for sub in subs_w_intab:
            _, outtab, cost = sub
            sub_fst_right = fst(intab_sub_symbol, outtab, cost)

            sub_graph_right=sub_graph_right|sub_fst_right

    return sub_graph_left, sub_graph_right

# ------------------------------- #
# functions for performing search #
# ------------------------------- #

@output_cache(os.path.dirname(__file__))
def search_word(
        form: str,
        num_hits: int = 10,
        edit_bound: int = 5,
        main_lemmatizer: Optional[pynini.Fst]=None,
        main_analyzer: Optional[pynini.Fst]=None,
        try_lower_bound: bool = True,
    ) -> List[Tuple[Dict[str, Any], float]]:
    """
    Returns fuzzy search hits for a queried word form across all parts of speech.

    Arguments:
        form:       str of form to query parses for
        num_hits:   int, number of parses to return
        edit_bound: int, maximum number of edits to allow in search
        main_lemmatizer: FST of main lemmatizer (optional)
        main_analyzer: FST of main analyzer (optional)
        try_lower_bound: bool, whether to try searching with lower edit bounds
            until `num_hits` are found (default: True)
    Returns:
        parses:     list of tuples, each of shape `(parse: dict, prob: float)`
    """
    if try_lower_bound:
        parses = []
        current_bound = 1
        while len(parses) < num_hits and current_bound < edit_bound:
            parses = search_word(
                form,
                num_hits,
                current_bound,
                main_lemmatizer,
                main_analyzer,
                try_lower_bound=False,
            )
            current_bound = min(current_bound+2, edit_bound)
        if len(parses) >= num_hits:
            return parses[:num_hits]

    left_factor, searchable_lexicon = get_searchable_main_parser(bound=edit_bound)
    query_fst = fst(form)@left_factor
    query_fst.optimize().arcsort()
    search_lattice = query_fst@searchable_lexicon
    search_lattice.project('output')
    search_lattice.optimize().arcsort()
    hits = get_lattice_strs_and_weights(
        search_lattice,
        nshortest=num_hits,
        strip_eos=False,
    )

    if main_lemmatizer is None or main_analyzer is None:
        main_lemmatizer, main_analyzer, _ = get_main_parser()
    parses = []
    for hit_str, weight in hits:
        for parse in parse_word(
            hit_str,
            main_lemmatizer,
            main_analyzer
        ):
            if not parse_is_root(parse):
                # skip zero-feature parses
                parse['weight']=weight
                parses.append(parse)
    return parses

def search_for_hyphenated_form(
        unparsed_form: str,
        lattice: pynini.Fst,
        num_hits: int = 10,
) -> str:
    """
    Arguments:
        unparsed_form:  str of form to search for
        lattice:        FST representing the lexicon to search
    """
    query_fst = fst(unparsed_form)@INSERT_HYPHEN_RULE
    search_lattice = query_fst@lattice
    search_lattice.optimize().arcsort()
    nbest_hits = get_lattice_strs_and_weights(
        search_lattice,
        nshortest=num_hits,
    )
    return nbest_hits
