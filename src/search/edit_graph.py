from string import ascii_lowercase
import graphviz
import pynini
from pynini.lib import pynutil
from pynini.lib.edit_transducer import EditTransducer
from pynini.lib.rewrite import lattice_to_nshortest
import numpy as np

DEFAULT_INSERT_COST = 1
DEFAULT_DELETE_COST = 1
DEFAULT_SUBSTITUTE_COST = 1
DEFAULT_EDIT_BOUND = 5

_edit_transducer = EditTransducer(alphabet=ascii_lowercase, bound=5)

ascii_table = pynini.SymbolTable()
ascii_table.add_symbol("<eps>")
alphabet = ["<eps>"] + list(ascii_lowercase)

symbol_range = (1, 256)

for i in range(*symbol_range):
    ascii_table.add_symbol(chr(i))


def set_symbols(fst: pynini.Fst):
    fst.set_input_symbols(ascii_table)
    fst.set_output_symbols(ascii_table)
    return fst


def print_fst(f):
    f = set_symbols(f)
    tmp_path = "./tmp/null.dot"
    f.draw(tmp_path, portrait=True)
    with open(tmp_path) as file:
        graph = graphviz.Source(file.read())
    graph.render(tmp_path.removesuffix(".dot") + ".gv")


def decode_lattice(lattice: pynini.Fst) -> list[tuple[str, float]]:
    result = []

    path_iter = lattice.paths()
    while not path_iter.done():
        label_iter = path_iter.olabels()
        label_chars = [ascii_table.find(label) for label in label_iter if label != 0]
        label_str = "".join(label_chars)
        weight = float(path_iter.weight())
        result.append((label_str, weight))
        path_iter.next()

    result.sort(key=lambda t: t[-1])
    return result


def get_search_graph(
    lexicon: pynini.Fst, right_factor: pynini.Fst | None = None
) -> pynini.Fst:
    if right_factor is None:
        right_factor = _edit_transducer._e_o

    search_graph = right_factor @ lexicon
    search_graph.optimize()
    return search_graph


def get_query_graph(
    query_str: pynini.Fst, left_factor: pynini.Fst | None = None
) -> pynini.Fst:
    if left_factor is None:
        left_factor = _edit_transducer._e_i

    query_graph = query_str @ left_factor
    query_graph.optimize()
    return query_graph


def intersect_graphs(
    query_graph: pynini.FstLike, search_graph: pynini.Fst, top_k: int = 5
) -> dict:
    lattice = query_graph @ search_graph
    lattice_num_states = lattice.num_states()
    lattice = lattice.project("output")
    lattice.optimize()
    top_k_lattice = lattice_to_nshortest(lattice, nshortest=top_k)
    result = decode_lattice(top_k_lattice)
    return {
        "result": result,
        "lattice_num_states": lattice_num_states,
    }


def prepare_cost_matrix_for_edit_graph(
    cost_matrix: np.ndarray, alphabet: list[str]
) -> dict:
    """
    Prepares a transition matrix for use in the edit graph by converting it to a dictionary format.
    The dictionary contains the keys "insertions", "deletions", and "substitutions",
    each mapping to a list of tuples that specify the edit operations and their associated
    probabilities.

    Args:
        cost_matrix: A 2D numpy array representing the transition probabilities between symbols.
        alphabet: A list of symbols representing the alphabet.

    Returns:
        A dictionary where keys are tuples of (input_symbol, output_symbol)
        and values are the corresponding probabilities.
    """
    substitutions: list[tuple[str, str, float]] = []
    insertions: list[tuple[str, float]] = []
    deletions: list[tuple[str, float]] = []

    for i, input_symbol in enumerate(alphabet):
        for j, output_symbol in enumerate(alphabet):
            if input_symbol == output_symbol:
                continue  # No edit operation for identical symbols
            elif input_symbol == "<eps>":
                insertions.append((output_symbol, cost_matrix[i, j]))
            elif output_symbol == "<eps>":
                deletions.append((input_symbol, cost_matrix[i, j]))
            else:
                substitutions.append((input_symbol, output_symbol, cost_matrix[i, j]))
                
    cost_dict = {
        "substitutions": substitutions,
        "insertions": insertions,
        "deletions": deletions,
    }

    return cost_dict

def get_edit_factors(
    insertions: list[tuple[pynini.FstLike, pynini.WeightLike]],
    substitutions: list[tuple[pynini.FstLike, pynini.FstLike, pynini.WeightLike]],
    deletions: list[tuple[pynini.FstLike, pynini.WeightLike]],
    sigma: pynini.FstLike,
    insert_cost: float = DEFAULT_INSERT_COST,
    sub_cost: float = DEFAULT_SUBSTITUTE_COST,
    delete_cost: float = DEFAULT_DELETE_COST,
    bound: int | None = DEFAULT_EDIT_BOUND,
) -> tuple[pynini.Fst, pynini.Fst]:
    """
    Arguments:
        insertions:     list of couples (insertion_element, insertion_cost) where `insertion_element`
                        is a str or FST and `insertion_cost` is a weight for inserting the element
        substitutions:  list of triples (sub_intab, sub_outtab, sub_cost) where `sub_intab` and `sub_outtab`
                        is the pair of strs or FSTs to substitute and `sub_cost` is a weight associated with
                        the substitution. Note `sub_intab` refers to elements in the **query** and `sub_outtab`
                        to elements in the **lexicon**.
        deletions:      list of couples (deletion_element, deletion_cost) where `deletion_element` is a str
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
    insert_graph_left, insert_graph_right = _get_insertion_graph(
        insertions, insert_cost, sigma
    )
    delete_graph_left, delete_graph_right = _get_deletion_graph(
        deletions, delete_cost, sigma
    )
    sub_graph_left, sub_graph_right = _get_substitution_graph(
        substitutions, sub_cost, sigma
    )

    edit_graph_left = (
        pynini.union(insert_graph_left, delete_graph_left, sub_graph_left)
        .optimize()
        .arcsort()
    )
    edit_graph_right = (
        pynini.union(insert_graph_right, delete_graph_right, sub_graph_right)
        .optimize()
        .arcsort()
    )

    left_factor = _compose_edit_graph_w_sigma(edit_graph_left, sigma, bound)
    right_factor = _compose_edit_graph_w_sigma(edit_graph_right, sigma, bound)

    left_factor.optimize().arcsort()
    right_factor.optimize().arcsort()

    return left_factor, right_factor


def _compose_edit_graph_w_sigma(
    edit_graph: pynini.Fst,
    sigma: pynini.Fst,
    bound: int | None = None,
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
    composed_factor = composed_factor.optimize().arcsort()
    return composed_factor


def _get_insertion_graph(
    insertions: list[tuple[str, pynini.WeightLike]],
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
    sigma_except_custom = sigma - insert_inputs
    sigma_except_custom_weighted = sigma_except_custom + pynini.accep(
        "", weight=insert_cost
    )
    insert_symbol = "[INSERT]"
    insert_graph_left = pynutil.insert(insert_symbol)
    insert_graph_right = pynini.Fst(insert_symbol, sigma_except_custom_weighted)
    for insert_str, cost in insertions:
        insertion_fst = pynini.Fst(insert_symbol, insert_str, cost)
        insert_graph_right = insert_graph_right | insertion_fst
    return insert_graph_left, insert_graph_right


def _get_deletion_graph(
    deletions: list[tuple[str, pynini.WeightLike]],
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
    sigma_except_custom = sigma - delete_inputs
    delete_symbol = f"[DELETE]"
    delete_graph_left = pynini.Fst(
        sigma_except_custom, delete_symbol, weight=delete_cost
    )
    for delete_str, cost in deletions:
        deletion_fst = pynini.Fst(delete_str, delete_symbol, cost)
        delete_graph_left = delete_graph_left | deletion_fst

    delete_graph_right = pynutil.delete(delete_symbol)
    return delete_graph_left, delete_graph_right


def _get_substitution_graph(
    substitutions: list[tuple[str, pynini.WeightLike]],
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
    intab_fst = pynini.union(*intabs)
    sigma_except_intabs = sigma - intab_fst
    sub_symbol = f"[SUBSTITUTE]"
    sub_acceptor = pynini.accep(sub_symbol)
    sub_graph_left = pynini.Fst(sigma_except_intabs, sub_acceptor)
    sub_graph_right = pynini.Fst(sub_acceptor, sigma, weight=sub_cost)

    # cache all intabs that have been accounted for
    # can't call `set` on intabs since pynini.Fst in unhashable
    used_intabs = []
    for i, intab in enumerate(intabs):
        if intab in used_intabs:
            continue
        intab_sub_symbol = f"[SUBSTITUTE{i}]"
        subs_w_intab = [sub for sub in substitutions if sub[0] == intab]

        outtabs_for_element = [sub[1] for sub in subs_w_intab]
        outtabs_fst = pynini.union(*outtabs_for_element)
        remaining_outtabs = sigma - outtabs_fst
        sub_fst_left = pynini.Fst(intab, intab_sub_symbol)
        sub_graph_left = sub_graph_left | sub_fst_left

        sub_fst_right = pynini.Fst(intab_sub_symbol, remaining_outtabs, sub_cost)
        sub_graph_right = sub_graph_right | sub_fst_right

        for sub in subs_w_intab:
            _, outtab, cost = sub
            sub_fst_right = pynini.Fst(intab_sub_symbol, outtab, cost)

            sub_graph_right = sub_graph_right | sub_fst_right

    return sub_graph_left, sub_graph_right
