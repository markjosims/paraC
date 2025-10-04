import pynini
from pynini.lib import pynutil

from typing import *
from src.fst_helpers import *
from src.constants import (
    INSERT, DELETE, SUBSTITUTE,
    DEFAULT_INSERT_COST, DEFAULT_DELETE_COST, DEFAULT_SUBSTITUTE_COST,
)
from src.phonology import SIGMA, INSERTION_COSTS, DELETION_COSTS, SUBSTITUTION_COSTS
from src.forms import FV2PARADIGM

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
    return left_factor, searchable_lexicon

def get_edit_factors(
        insertions: List[Tuple[pynini.FstLike, pynini.WeightLike]],
        substitutions: List[Tuple[pynini.FstLike, pynini.FstLike, pynini.WeightLike]],
        deletions: List[Tuple[pynini.FstLike, pynini.WeightLike]],
        sigma: pynini.FstLike,
        insert_cost: float=DEFAULT_INSERT_COST,
        sub_cost: float=DEFAULT_SUBSTITUTE_COST,
        delete_cost: float=DEFAULT_DELETE_COST,
        bound: Optional[int]=None,
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
        sub_cost:       Default cost for substituting any element not specified in `substiutions`.
        bound:          Integer indicating the number of edits allowed when searching. Defaults to unbounded (infinite edits allowed)

    Returns:
        (left_factor, right_factor):    FSTs for the left and right factors.

    Compiles FSTs representing an edit transducer allowing for custom weights for particular edits, as specified in `insertions`,
    `deletions` and `substitutions`. Returns left and right factors for searching. Usage for searching is `query@left_factor@right_factor@lexicon`.
    """
    insert_graph_left, insert_graph_right = _get_insertion_graph(insertions, insert_cost, sigma)
    delete_graph_left, delete_graph_right = _get_deletion_graph(deletions, delete_cost, sigma)
    sub_graph_left, sub_graph_right = _get_substitution_graph(substitutions, sub_cost, sigma)

    edit_graph_left = pynini.union(insert_graph_left, delete_graph_left, sub_graph_left).optimize()
    edit_graph_right = pynini.union(insert_graph_right, delete_graph_right, sub_graph_right).optimize()
    
    left_factor = _compose_edit_graph_w_sigma(edit_graph_left, sigma, bound)
    right_factor = _compose_edit_graph_w_sigma(edit_graph_right, sigma, bound)

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
    composed_factor=composed_factor.optimize()
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

def search_verb_form(
        verb_form: str,
        num_hits: int = 5,
        edit_bound: int = 5,
    ) -> List[Tuple[Dict[str, Any], float]]:
    """
    Arguments:
        verb_form:  str of verb form to query parses for
        num_hits:   int, number of parses to return
    Returns:
        parses:     list of tuples, each of shape `(parse: dict, prob: float)`
    
    Performs fuzzy search mapping a queried verb form to possible parses
    as defined by verb paradigm FSTs. Returns list of couples of (`parse`, `prob`).
    `parse` is output of `parse_inflected_verb`
    and `prob` is a normalized weight indicating the probability
    of the given parse relative to other parses, calculated using
    a softmax over the inverse cost of each hit. List is sorted
    by probability in descending order so that most likely hit is the first item.
    """

    hits = []
    left_factor, right_factor = get_edit_factors(
        sigma=SIGMA,
        insertions=INSERTION_COSTS,
        substitutions=SUBSTITUTION_COSTS,
        deletions=DELETION_COSTS,
        bound=edit_bound,
    )
    query_fst = fst(verb_form)@left_factor
    query_fst.optimize()
    for fv, paradigm in FV2PARADIGM.items():
        # since we cannot know ahead of time what paradigm nbest hits will come from
        # get nbest hits for each paradigm individually, then filter later
        paradigm_lattice = paradigm.lemmatizer
        paradigm_lattice = pynini.project(paradigm_lattice, 'input')
        paradigm_lattice.optimize()
        search_lattice = query_fst@right_factor@paradigm_lattice
        search_lattice.optimize()
        hits_for_paradigm = get_nbest_strs_and_weights(
            search_lattice,
            n=num_hits,
            return_input_strs=False,
            use_byte_tokens=True,
        )
        
        hits.extend([(hit, fv, weight) for hit, weight in hits_for_paradigm])
    hits.sort(key=lambda hit_tuple: hit_tuple[-1])
    nbest_hits = hits[:num_hits]
    return nbest_hits
