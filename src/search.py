import pynini
from pynini.lib import pynutil
from pynini.lib.edit_transducer import (
    EditTransducer,
    DEFAULT_INSERT_COST,
    DEFAULT_SUBSTITUTE_COST,
    DEFAULT_DELETE_COST
)
from typing import *

INSERT = EditTransducer.INSERT
DELETE = EditTransducer.DELETE
SUBSTITUTE = EditTransducer.SUBSTITUTE

def get_searchable_lexicon(
        lexicon: Union[List[str], pynini.FstLike],
        **edit_factor_kwargs,
    ):
    if type(lexicon) is list:
        lexicon = pynini.union(*lexicon)
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
    ):
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
    insert_inputs = pynini.union(*[insert[0] for insert in insertions])
    sigma_except_custom = sigma-insert_inputs
    sigma_except_custom_weighted = sigma_except_custom + pynini.accep('', insert_cost)
    insert_symbol = f"[{INSERT}]"
    insert_graph_left = pynutil.insert(insert_symbol, insert_cost)
    insert_graph_right = pynini.cross(insert_symbol, sigma_except_custom_weighted)
    for (insert_str, cost) in insertions:
        insert_graph_right=insert_graph_right|pynini.cross(insert_symbol, pynini.accep(insert_str, cost))
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
    delete_inputs = pynini.union(*[delete[0] for delete in deletions])
    sigma_except_custom = sigma-delete_inputs
    delete_symbol = f"[{DELETE}]"
    delete_graph_left = pynini.cross(sigma_except_custom, pynini.accep(delete_symbol, delete_cost))
    for (delete_str, cost) in deletions:
        delete_graph_left=delete_graph_left|pynini.cross(delete_str, pynini.accep(delete_symbol, cost))

    delete_graph_right = pynutil.delete(delete_symbol)
    return delete_graph_left, delete_graph_right
    
def _get_substitution_graph(
        substitutions: List[Tuple[str, pynini.WeightLike]],
        sub_cost: pynini.WeightLike,
        sigma: pynini.Fst,
    ) -> pynini.Fst:
    """
    Arguments:
        substitutions: list of tuples of strings and custom sub weights per string
        sub_cost: default weight for substitution
        sigma: FSA of alphabet

    Returns:
        sub_graph_left, sub_graph_right: left and right factors for calculating substitution costs

    Builds the left factor as an FST mapping each element on the alphabet to the substitution symbol,
    where the default symbol is used for any pair of elements not specified in `substitutions`.
    Else, for each intab in `substitutions` map to a unique symbol (by adding an index to the original symbol).
    Builds the right factor as an FST mapping the default symbol to any element on the alphabet and each
    special symbol to its appropriate outtab, i.e.:

        Left factor                     Right factor
        \sigma  --> <substitution>      --> \sigma
        d       --> <substitution_1>    --> e
        f       --> <substitution_2>    --> g

    If d>e and f>g are specifically defined in the custom substitutions.

    Weight values from `substitutions` or `sub_cost` are used for the left factor.
    Arcs on the right factor use semiring Zero.

    Note that custom substitutions must have a weight strictly less than the default substitution weight,
    otherwise they will be overridden by \sigma --> \sigma arc.
    """
    intabs = pynini.union(*[sub[0] for sub in substitutions])
    sigma_except_intabs = sigma-intabs
    sub_symbol = f"[{SUBSTITUTE}]"
    sub_graph_left = pynini.cross(sigma_except_intabs, pynini.accep(sub_symbol, sub_cost))
    sub_graph_right = pynini.cross(sub_symbol, sigma_except_intabs)
    for i, sub in enumerate(substitutions):
        intab, outtab, cost = sub
        sub_symbol_i = f"[{SUBSTITUTE.removesuffix('>')}{i}>]"
        sub_graph_left=sub_graph_left|pynini.cross(intab, pynini.accep(sub_symbol_i, cost))
        sub_graph_right=sub_graph_right|pynini.cross(sub_symbol_i, outtab)

    return sub_graph_left, sub_graph_right

def get_min_path_weight(f: pynini.Fst) -> float:
    """
    Arguments:
        f:  FST to calculate path weight for
    Returns:
        path_weight: float indicating weight of shortest path.
    """
    f_shortest = pynini.shortestpath(f)
    path_weight = 0
    for state in f_shortest.states():
        state_arcs = list(f_shortest.arcs(state))
        assert len(state_arcs)<=1
        for arc in state_arcs:
            path_weight+=float(arc.weight)
        final_weight = f_shortest.final(state)
        weight_type = f_shortest.weight_type()
        if final_weight != pynini.Weight.zero(weight_type):
            path_weight+=float(final_weight)
    return path_weight
